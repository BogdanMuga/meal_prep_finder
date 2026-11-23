"""Flask web app: the search and Browse pages, a recipe editor, and a small JSON API.

Recipes are stored in SQLite (see db.py). An empty database is filled from
data/recipes.json on startup.

Configuration (environment variables):
  MEAL_PREP_DATABASE_URL  SQLAlchemy URL; default sqlite file data/recipes.db in the project
  ADMIN_ENABLED=1         turn on the /admin recipe editor (local use only)
  SECRET_KEY              signs sessions/CSRF tokens; random per run if unset
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

import click
from flask import Flask, abort, current_app, jsonify, render_template, request, url_for
from flask_migrate import Migrate, upgrade
from flask_wtf.csrf import CSRFProtect

from .countries import country_flag, slugify
from .db import RecipeRow, db, export_recipes_json, is_empty, load_recipes_from_db, seed
from .editor import editor
from .matcher import RecipeIndex
from .models import DEFAULT_DATA, Recipe, load_recipes

MAX_LIMIT = 100
MIGRATIONS_DIR = str(Path(__file__).parent / "migrations")
# One database for every way of running from the project (run_app.py and the
# `python -m flask` commands): <project>/data/recipes.db. In the packaged exe this
# is _internal/data/recipes.db, the same file run_app.py picks there.
DEFAULT_DATABASE = Path(__file__).resolve().parent.parent / "data" / "recipes.db"
IN_MEMORY = "sqlite://"
GENERAL_SLUG = "general"  # /countries/general: recipes with no country of origin

csrf = CSRFProtect()
migrate = Migrate()


class Catalog:
    """The recipes the pages show, rebuilt from the database after every edit."""

    def __init__(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.index = RecipeIndex(load_recipes_from_db())
        self.by_id = {recipe.id: recipe for recipe in self.index.recipes}
        # the photo mosaic in the page header
        self.gallery = [recipe.image for recipe in self.index.recipes if recipe.image][:12]


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _setup_database(app: Flask, recipes: list[Recipe] | None) -> None:
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    if uri == IN_MEMORY or ":memory:" in uri:
        db.create_all()
    else:
        if uri.startswith("sqlite:///"):  # make sure the database file's folder exists
            Path(uri.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        upgrade(directory=MIGRATIONS_DIR)  # creates the tables on first run, applies new migrations later
    if is_empty():
        seed(recipes if recipes is not None else load_recipes())


def create_app(recipes: list[Recipe] | None = None, config: dict | None = None) -> Flask:
    """Build the app. Passing `recipes` uses a private in-memory database seeded
    with them (handy for experiments); otherwise the configured database is used."""
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        SQLALCHEMY_DATABASE_URI=os.environ.get("MEAL_PREP_DATABASE_URL")
        or "sqlite:///" + str(DEFAULT_DATABASE),
        ADMIN_ENABLED=_env_flag("ADMIN_ENABLED"),
        PHOTO_DIR=str(Path(app.static_folder) / "recipes"),
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,   # photo uploads
        WTF_CSRF_TIME_LIMIT=None,
    )
    if recipes is not None:
        app.config["SQLALCHEMY_DATABASE_URI"] = IN_MEMORY
    app.config.update(config or {})

    db.init_app(app)
    migrate.init_app(app, db, directory=MIGRATIONS_DIR)
    csrf.init_app(app)
    app.register_blueprint(editor)
    with app.app_context():
        if not _env_flag("MEAL_PREP_SKIP_DB_SETUP"):  # set only while running `flask db` commands
            _setup_database(app, recipes)
            app.extensions["catalog"] = Catalog()

    app.jinja_env.filters["flag"] = country_flag

    def catalog() -> Catalog:
        return app.extensions["catalog"]

    @app.context_processor
    def values_for_every_page() -> dict:
        """The recipe count and the header photo mosaic, which base.html shows on every page."""
        current = app.extensions.get("catalog")
        if current is None:  # no database (while running `flask db` commands)
            return {}
        return {"total": len(current.index.recipes), "gallery": current.gallery}

    @app.template_filter("photo")
    def photo(image: str, small: bool = False) -> str:
        """URL for a recipe photo. Local paths are served from static/; with
        small=True the '<name>-small.jpg' thumbnail is used when it exists.
        A ?v=<mtime> suffix makes browsers fetch a replaced photo again.
        Full http(s) URLs are passed through unchanged."""
        if not image or image.startswith(("http://", "https://")):
            return image
        static = Path(app.static_folder)
        if small:
            photo_path = Path(image)
            thumb = photo_path.with_name(f"{photo_path.stem}-small{photo_path.suffix}").as_posix()
            if (static / thumb).is_file():
                image = thumb
        photo_file = static / image
        version = int(photo_file.stat().st_mtime) if photo_file.is_file() else None
        return url_for("static", filename=image, v=version)

    def _tile(name: str, slug: str, flag: str, recipes: list[Recipe]) -> dict:
        """One Browse tile: a country, or 'General'."""
        return {"name": name, "slug": slug, "flag": flag, "count": len(recipes),
                "image": next((recipe.image for recipe in recipes if recipe.image), ""),
                "recipes": recipes}

    def _country_tiles() -> list[dict]:
        index = catalog().index
        return [_tile(name, slugify(name), country_flag(name), index.by_country(name))
                for name, _ in index.countries()]

    def _general_recipes() -> list[Recipe]:
        return sorted((recipe for recipe in catalog().index.recipes if not recipe.country),
                      key=lambda recipe: recipe.name)

    def _browse_tiles() -> list[dict]:
        """The Browse page tiles: 'General' (recipes with no country) first, then countries A-Z."""
        general = _general_recipes()
        tiles = [_tile("General", GENERAL_SLUG, "🍽️", general)] if general else []
        return tiles + _country_tiles()

    def _browse_page(**page_values):
        return render_template("browse.html", tab="browse", **page_values)

    def _read_params():
        q = (request.args.get("q") or "").strip()
        mode = request.args.get("mode", "any")
        if mode not in ("any", "all"):
            abort(400, description="mode must be 'any' or 'all'")
        limit_raw = request.args.get("limit")
        limit = None
        if limit_raw:
            try:
                limit = int(limit_raw)
            except ValueError:
                abort(400, description="limit must be an integer")
            if not 1 <= limit <= MAX_LIMIT:
                abort(400, description=f"limit must be between 1 and {MAX_LIMIT}")
        return q, mode, limit

    @app.get("/")
    def home():
        q, mode, limit = _read_params()
        response = catalog().index.search(q, mode=mode, limit=limit) if q else None
        return render_template("index.html", q=q, mode=mode, response=response, tab="search")

    @app.get("/countries")
    @app.get("/countries/<slug>")
    def browse(slug: str | None = None):
        tiles = _browse_tiles()
        selected = None
        if slug is not None:
            selected = next((tile for tile in tiles if tile["slug"] == slug), None)
            if selected is None:  # unknown country: show the tiles, with a note
                return _browse_page(view="origin", tiles=tiles, selected=None,
                                    recipes=[], missing=True), 404
        return _browse_page(view="origin", tiles=tiles, selected=selected,
                            recipes=selected["recipes"] if selected else [])

    @app.get("/recipes")
    def all_recipes():
        recipes = sorted(catalog().index.recipes, key=lambda recipe: recipe.name)
        return _browse_page(view="all", tiles=[], selected=None, recipes=recipes)

    @app.get("/api/search")
    def api_search():
        q, mode, limit = _read_params()
        if not q:
            return jsonify(error="query parameter 'q' is required"), 400
        return jsonify(catalog().index.search(q, mode=mode, limit=limit).to_dict())

    @app.get("/api/recipes")
    def api_recipes():
        index = catalog().index
        country = (request.args.get("country") or "").strip()
        recipes = index.by_country(country) if country else index.recipes
        return jsonify([recipe.to_dict() for recipe in recipes])

    @app.get("/api/countries")
    def api_countries():  # real countries only; 'General' is a page grouping, not a country
        return jsonify([{"country": tile["name"], "slug": tile["slug"], "flag": tile["flag"],
                         "count": tile["count"]} for tile in _country_tiles()])

    @app.get("/api/recipes/<recipe_id>")
    def api_recipe(recipe_id: str):
        recipe = catalog().by_id.get(recipe_id)
        if recipe is None:
            return jsonify(error=f"recipe '{recipe_id}' not found"), 404
        return jsonify(recipe.to_dict())

    @app.errorhandler(404)
    def not_found(err):
        if request.path.startswith("/api/"):
            return jsonify(error="not found"), 404
        return render_template("not_found.html"), 404

    @app.errorhandler(400)
    def bad_request(err):
        return jsonify(error=err.description), 400

    # --- command line -------------------------------------------------------------------

    @app.cli.command("init-db")
    @click.option("--reset", is_flag=True,
                  help="Delete every recipe in the database and reload recipes.json.")
    def init_db_command(reset: bool):
        """Create the database (if needed) and fill it from recipes.json."""
        if reset:
            click.confirm("This deletes all recipes in the database, including edits you "
                          "haven't exported. Continue?", abort=True)
            db.session.execute(db.delete(RecipeRow))
            db.session.commit()
        if is_empty():
            count = seed(load_recipes())
            click.echo(f"Loaded {count} recipes from {DEFAULT_DATA.name}.")
        else:
            count = len(load_recipes_from_db())
            click.echo(f"The database is ready with {count} recipes. "
                       "(It fills itself from recipes.json when empty; use --reset to reload it.)")
        click.echo(f"Database: {current_app.config['SQLALCHEMY_DATABASE_URI']}")

    @app.cli.command("export-recipes")
    @click.option("--path", type=click.Path(dir_okay=False, path_type=Path), default=DEFAULT_DATA,
                  show_default=True, help="Where to write the JSON.")
    def export_command(path: Path):
        """Write every recipe in the database to recipes.json."""
        count = export_recipes_json(path)
        click.echo(f"Wrote {count} recipes to {path}.")

    return app


if __name__ == "__main__":
    create_app().run(debug=True)

"""The recipe editor (under /admin): list, create, edit and delete recipes, and upload photos.

Off unless the app is started with ADMIN_ENABLED=1. There are no user accounts:
it is meant for a copy running on your own PC (the dev server only listens on
127.0.0.1). Every form carries a CSRF token (Flask-WTF).
"""

from __future__ import annotations

import re
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, redirect, render_template, url_for
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from PIL import Image, UnidentifiedImageError
from wtforms import BooleanField, IntegerField, SelectField, StringField, TextAreaField
from wtforms.fields import SelectChoice
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from .countries import COUNTRY_CODES, NATIONAL_CUISINES, slugify
from .db import RecipeRow, db, next_position
from .models import BASIC_FIELDS, DIFFICULTIES, NUTRITION_FIELDS, Recipe

# The URL stays /admin (and the switch ADMIN_ENABLED / --admin) so bookmarks keep working.
editor = Blueprint("editor", __name__, url_prefix="/admin")

SLUG_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
PHOTO_FORMATS = {"JPEG", "PNG", "WEBP"}
FULL_WIDTH, SMALL_WIDTH = 700, 350
REGIONAL_STYLES = ("Cajun", "Tex-Mex", "Mediterranean")


@editor.before_request
def _only_when_enabled():
    if not current_app.config.get("ADMIN_ENABLED"):
        abort(404)


def _catalog():
    return current_app.extensions["catalog"]


# --- form ---------------------------------------------------------------------------

class RecipeForm(FlaskForm):
    id = StringField("ID (URL name)", validators=[Optional(), Length(max=80)],
                     description="Lowercase words joined by dashes, e.g. lemon-chicken-bowls. "
                                 "Leave empty to make one from the name.")
    name = StringField("Name", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("Description", validators=[Optional()])
    country = SelectField("Country", choices=[SelectChoice("", "— none (generic dish) —")]
                          + [SelectChoice(country_name, country_name)
                             for country_name in sorted(COUNTRY_CODES)])
    cuisine = StringField("Regional style", validators=[Optional(), Length(max=80)],
                          description="Only for a style that isn't one country, e.g. "
                                      + ", ".join(REGIONAL_STYLES) + ". Leave empty otherwise.")
    difficulty = SelectField("Difficulty", choices=[SelectChoice(level, level.capitalize())
                                                    for level in DIFFICULTIES])
    servings = IntegerField("Servings", default=4, validators=[DataRequired(), NumberRange(min=1)])
    prep_minutes = IntegerField("Prep (min)", default=0, validators=[Optional(), NumberRange(min=0)])
    cook_minutes = IntegerField("Cook (min)", default=0, validators=[Optional(), NumberRange(min=0)])
    fridge_days = IntegerField("Keeps in fridge (days)", default=4, validators=[Optional(), NumberRange(min=0)])
    freezer_months = IntegerField("Freezes (months, 0 = no)", default=0, validators=[Optional(), NumberRange(min=0)])
    calories = IntegerField("Calories", validators=[Optional(), NumberRange(min=0)])
    protein_g = IntegerField("Protein (g)", validators=[Optional(), NumberRange(min=0)])
    carbs_g = IntegerField("Carbs (g)", validators=[Optional(), NumberRange(min=0)])
    fat_g = IntegerField("Fat (g)", validators=[Optional(), NumberRange(min=0)])
    fiber_g = IntegerField("Fiber (g)", validators=[Optional(), NumberRange(min=0)])
    tags = StringField("Tags", description="Comma-separated, e.g. high-protein, gluten-free")
    equipment = TextAreaField("Equipment", description="One per line")
    ingredients = TextAreaField("Ingredients", validators=[DataRequired()], description="One per line")
    steps = TextAreaField("Method", description="One step per line")
    storage = TextAreaField("Storage", validators=[Optional()])
    reheat = TextAreaField("Reheat", validators=[Optional()])
    tips = TextAreaField("Tips", description="One per line")
    photo = FileField("Photo", validators=[FileAllowed(["jpg", "jpeg", "png", "webp"], "JPEG, PNG or WebP only")],
                      description="JPEG, PNG or WebP. Resized to 700 px plus a 350 px thumbnail.")
    remove_photo = BooleanField("Remove the current photo")

    ONE_PER_LINE = ("equipment", "ingredients", "steps", "tips")  # tags are comma-separated

    def fill_from(self, recipe: Recipe) -> None:
        for name in ("id", *BASIC_FIELDS):
            if name in self:  # the photo is uploaded, not typed, so "image" has no field
                self[name].data = getattr(recipe, name)
        self.tags.data = ", ".join(recipe.tags)
        for name in self.ONE_PER_LINE:
            self[name].data = "\n".join(getattr(recipe, name))
        if recipe.nutrition:
            for name in NUTRITION_FIELDS:
                self[name].data = getattr(recipe.nutrition, name)

    def to_dict(self, recipe_id: str, image: str) -> dict:
        def lines(text):
            return [line.strip() for line in (text or "").splitlines() if line.strip()]

        data = {
            "id": recipe_id, "image": image,
            "name": self.name.data.strip(),
            "description": (self.description.data or "").strip(),
            "country": self.country.data or "",
            "cuisine": (self.cuisine.data or "").strip(),
            "difficulty": self.difficulty.data,
            "servings": self.servings.data,
            "storage": (self.storage.data or "").strip(),
            "reheat": (self.reheat.data or "").strip(),
            "tags": [tag.strip() for tag in (self.tags.data or "").split(",") if tag.strip()],
            **{name: lines(self[name].data) for name in self.ONE_PER_LINE},
        }
        for name in ("prep_minutes", "cook_minutes", "fridge_days", "freezer_months"):
            data[name] = self[name].data or 0
        nutrition = {name: self[name].data for name in NUTRITION_FIELDS
                     if self[name].data is not None}
        if nutrition:
            data["nutrition"] = nutrition
        return data


def _quality_problems(recipe: Recipe) -> list[str]:
    """Data-quality rules every saved recipe must meet, so an exported
    recipes.json stays clean."""
    problems = []
    if recipe.cuisine in NATIONAL_CUISINES:
        problems.append(f'"{recipe.cuisine}" is a national cuisine: pick '
                        f'{NATIONAL_CUISINES[recipe.cuisine]} as the country instead and leave '
                        "regional style empty.")
    nutrition = recipe.nutrition
    if (nutrition and nutrition.macro_calories
            and abs(nutrition.calories - nutrition.macro_calories) > 0.05 * nutrition.macro_calories):
        problems.append(f"Calories ({nutrition.calories}) should be within 5% of what the macros "
                        f"add up to ({nutrition.macro_calories} = 4×protein + 4×carbs + 9×fat).")
    if ("freezer-friendly" in recipe.tags) != recipe.freezer_friendly:
        problems.append('Use the "freezer-friendly" tag exactly when "Freezes (months)" is above 0.')
    return problems


# --- photos ---------------------------------------------------------------------------

def _photo_dir() -> Path:
    return Path(current_app.config["PHOTO_DIR"])


def _stored_image(recipe_id: str) -> str:
    """The image value saved on a recipe whose photo was uploaded in the editor."""
    return f"recipes/{recipe_id}.jpg"


def _photo_paths(recipe_id: str) -> tuple[Path, Path]:
    folder = _photo_dir()
    return folder / f"{recipe_id}.jpg", folder / f"{recipe_id}-small.jpg"


def save_photo(file_storage, recipe_id: str) -> str:
    """Validate an upload by its content (not its name), save a 700 px JPEG and a
    350 px thumbnail, and return the image path stored on the recipe."""
    try:
        img = Image.open(file_storage.stream)
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("That file isn't an image Pillow can read.") from exc
    if img.format not in PHOTO_FORMATS:
        raise ValueError(f"{img.format} images aren't supported; use JPEG, PNG or WebP.")
    img = img.convert("RGB")
    full, small = _photo_paths(recipe_id)
    full.parent.mkdir(parents=True, exist_ok=True)
    for path, width in ((full, FULL_WIDTH), (small, SMALL_WIDTH)):
        resized = img.copy()
        resized.thumbnail((width, width * 4))
        resized.save(path, "JPEG", quality=85, optimize=True)
    return _stored_image(recipe_id)


def delete_photo(recipe_id: str, image: str) -> None:
    """Remove the photo files this editor manages for the recipe (never other files)."""
    if image != _stored_image(recipe_id):
        return
    for path in _photo_paths(recipe_id):
        path.unlink(missing_ok=True)


# --- routes -----------------------------------------------------------------------------

@editor.get("/")
def index():
    return render_template("editor/list.html", recipes=_catalog().index.recipes, tab="editor")


def _save_recipe(form: RecipeForm, row: RecipeRow | None):
    """Validate and store the form. Returns (row, errors)."""
    is_new = row is None
    recipe_id = row.id if row else ((form.id.data or "").strip() or slugify(form.name.data or ""))
    errors: list[str] = []
    if not SLUG_RE.fullmatch(recipe_id):
        errors.append("ID must be lowercase letters and digits joined by single dashes.")
    elif is_new and db.session.get(RecipeRow, recipe_id):
        errors.append(f'A recipe with ID "{recipe_id}" already exists.')
    name = (form.name.data or "").strip()
    clash = db.session.scalar(db.select(RecipeRow).where(db.func.lower(RecipeRow.name) == name.lower()))
    if clash and clash.id != recipe_id:
        errors.append(f'Another recipe is already called "{name}".')

    image = row.image if row else ""
    if errors:
        return None, errors
    try:
        recipe = Recipe.from_dict(form.to_dict(recipe_id, image))
    except (ValueError, TypeError) as exc:
        return None, [str(exc)]
    errors = _quality_problems(recipe)
    if errors:
        return None, errors

    upload = form.photo.data
    if upload and getattr(upload, "filename", ""):
        try:
            image = save_photo(upload, recipe_id)
        except ValueError as exc:
            return None, [str(exc)]
    elif form.remove_photo.data and image:
        delete_photo(recipe_id, image)
        image = ""
    recipe = Recipe.from_dict(form.to_dict(recipe_id, image))

    if is_new:
        row = RecipeRow.from_recipe(recipe, next_position())
        db.session.add(row)
    else:
        row.update_from(recipe)
    db.session.commit()
    _catalog().refresh()
    return row, []


def _render_form(form, row, errors, status=200):
    return render_template("editor/form.html", form=form, row=row, errors=errors, tab="editor",
                           regional_styles=REGIONAL_STYLES), status


@editor.route("/new", methods=["GET", "POST"])
def new():
    form = RecipeForm()
    if form.validate_on_submit():
        row, errors = _save_recipe(form, None)
        if not errors:
            flash(f"Added “{row.name}”.")
            return redirect(url_for("editor.index"))
        return _render_form(form, None, errors, 422)
    if form.is_submitted():
        return _render_form(form, None, [], 422)
    return _render_form(form, None, [])


@editor.route("/<recipe_id>/edit", methods=["GET", "POST"])
def edit(recipe_id: str):
    row = db.get_or_404(RecipeRow, recipe_id)
    form = RecipeForm()
    if form.validate_on_submit():
        saved, errors = _save_recipe(form, row)
        if not errors:
            flash(f"Saved “{saved.name}”.")
            return redirect(url_for("editor.index"))
        db.session.rollback()
        return _render_form(form, row, errors, 422)
    if form.is_submitted():
        return _render_form(form, row, [], 422)
    form.fill_from(row.to_recipe())
    return _render_form(form, row, [])


class DeleteForm(FlaskForm):
    pass


@editor.route("/<recipe_id>/delete", methods=["GET", "POST"])
def delete(recipe_id: str):
    row = db.get_or_404(RecipeRow, recipe_id)
    form = DeleteForm()
    if form.validate_on_submit():
        name, image = row.name, row.image
        db.session.delete(row)
        db.session.commit()
        delete_photo(recipe_id, image)
        _catalog().refresh()
        flash(f"Deleted “{name}”.")
        return redirect(url_for("editor.index"))
    return render_template("editor/delete.html", row=row, form=form, tab="editor")

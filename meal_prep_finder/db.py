"""SQLite storage for recipes (SQLAlchemy via Flask-SQLAlchemy).

The database is the live copy that the in-app editor changes. `data/recipes.json`
is the seed: an empty database is filled from it, and the `export-recipes` command
writes the database back to it in the same hand-readable layout.

Rows convert to and from the frozen `models.Recipe` dataclass, and every
conversion goes through `Recipe.from_dict`, so validation lives in one place.
"""

from __future__ import annotations

import json
from pathlib import Path

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import JSON, Integer, String, Text, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .models import BASIC_FIELDS, LIST_FIELDS, NUTRITION_FIELDS, Recipe


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


class RecipeRow(db.Model):
    __tablename__ = "recipes"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, index=True)  # display / file order
    name: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    image: Mapped[str] = mapped_column(String(300), default="")
    cuisine: Mapped[str] = mapped_column(String(80), default="")
    country: Mapped[str] = mapped_column(String(80), default="", index=True)
    difficulty: Mapped[str] = mapped_column(String(10), default="easy")
    servings: Mapped[int] = mapped_column(Integer, default=4)
    prep_minutes: Mapped[int] = mapped_column(Integer, default=0)
    cook_minutes: Mapped[int] = mapped_column(Integer, default=0)
    fridge_days: Mapped[int] = mapped_column(Integer, default=4)
    freezer_months: Mapped[int] = mapped_column(Integer, default=0)
    storage: Mapped[str] = mapped_column(Text, default="")
    reheat: Mapped[str] = mapped_column(Text, default="")
    # Nutrition per serving: all NULL, or all set.
    calories: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protein_g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    carbs_g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fat_g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fiber_g: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Ordered lists, always read and written whole.
    tags: Mapped[list] = mapped_column(JSON, default=list)
    equipment: Mapped[list] = mapped_column(JSON, default=list)
    ingredients: Mapped[list] = mapped_column(JSON, default=list)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    tips: Mapped[list] = mapped_column(JSON, default=list)

    # -- conversion --

    def to_dict(self) -> dict:
        """The recipes.json shape (what Recipe.from_dict reads)."""
        data = {"id": self.id}
        for field in BASIC_FIELDS:
            data[field] = getattr(self, field)
        for field in LIST_FIELDS:
            data[field] = list(getattr(self, field) or [])
        if self.calories is not None:
            data["nutrition"] = {field: getattr(self, field) or 0 for field in NUTRITION_FIELDS}
        return data

    def to_recipe(self) -> Recipe:
        return Recipe.from_dict(self.to_dict())

    def update_from(self, recipe: Recipe) -> None:
        for field in BASIC_FIELDS:
            setattr(self, field, getattr(recipe, field))
        for field in LIST_FIELDS:
            setattr(self, field, list(getattr(recipe, field)))
        nutrition = recipe.nutrition
        for field in NUTRITION_FIELDS:
            setattr(self, field, getattr(nutrition, field) if nutrition else None)

    @classmethod
    def from_recipe(cls, recipe: Recipe, position: int) -> "RecipeRow":
        row = cls(id=recipe.id, position=position)
        row.update_from(recipe)
        return row


# --- queries ------------------------------------------------------------------------

def _rows_in_order() -> list[RecipeRow]:
    """Every recipe row, in display / file order."""
    return list(db.session.scalars(select(RecipeRow).order_by(RecipeRow.position, RecipeRow.id)))


def load_recipes_from_db() -> list[Recipe]:
    return [row.to_recipe() for row in _rows_in_order()]


def next_position() -> int:
    return (db.session.scalar(select(func.max(RecipeRow.position))) or 0) + 1


def seed(recipes: list[Recipe]) -> int:
    """Insert recipes into an empty table, keeping their order. Returns the count."""
    db.session.add_all(RecipeRow.from_recipe(recipe, position)
                       for position, recipe in enumerate(recipes, 1))
    db.session.commit()
    return len(recipes)


def is_empty() -> bool:
    return db.session.scalar(select(func.count()).select_from(RecipeRow)) == 0


# --- recipes.json writer ---------------------------------------------------------------

def _to_json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _json_list_lines(key: str, items: list, indent: str = "    ") -> str:
    """A JSON list written one item per line ([] and one-item lists stay on one line)."""
    if len(items) <= 1:
        return f'{indent}"{key}": {_to_json(list(items))}'
    inner = ",\n".join(f"{indent}  {_to_json(item)}" for item in items)
    return f'{indent}"{key}": [\n{inner}\n{indent}]'


def format_recipes_json(recipes: list[dict]) -> str:
    """Render recipes in the hand-edited layout of data/recipes.json: short fields
    grouped on a line, long lists one item per line."""
    blocks = []
    for recipe in recipes:
        lines = [f'    "id": {_to_json(recipe["id"])}']
        if recipe.get("image"):
            lines.append(f'    "image": {_to_json(recipe["image"])}')
        lines.append(f'    "name": {_to_json(recipe["name"])}')
        lines.append(f'    "description": {_to_json(recipe.get("description", ""))}')
        origin = [f'"{key}": {_to_json(recipe[key])}' for key in ("cuisine", "country")
                  if recipe.get(key)]
        difficulty = f'"difficulty": {_to_json(recipe.get("difficulty", "easy"))}'
        lines.append("    " + ", ".join(origin + [difficulty]))
        lines.append("    " + ", ".join(
            f'"{key}": {recipe.get(key, 0)}' for key in
            ("servings", "prep_minutes", "cook_minutes", "fridge_days", "freezer_months")))
        lines.append(f'    "tags": {_to_json(recipe.get("tags", []))}')
        if recipe.get("nutrition"):
            lines.append(f'    "nutrition": {_to_json(recipe["nutrition"])}')
        lines.append(f'    "equipment": {_to_json(recipe.get("equipment", []))}')
        lines.append(_json_list_lines("ingredients", recipe.get("ingredients", [])))
        lines.append(_json_list_lines("steps", recipe.get("steps", [])))
        for key in ("storage", "reheat"):
            if recipe.get(key):
                lines.append(f'    "{key}": {_to_json(recipe[key])}')
        lines.append(_json_list_lines("tips", recipe.get("tips", [])))
        blocks.append("  {\n" + ",\n".join(lines) + "\n  }")
    return "[\n" + ",\n".join(blocks) + "\n]\n"


def export_recipes_json(path: Path) -> int:
    rows = _rows_in_order()
    path.write_text(format_recipes_json([row.to_dict() for row in rows]),
                    encoding="utf-8", newline="")
    return len(rows)

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .countries import NATIONAL_CUISINES

DEFAULT_DATA = Path(__file__).parent / "data" / "recipes.json"

DIFFICULTIES = ("easy", "medium", "hard")

# A recipe's fields, grouped the way the database and the editor handle them.
# The id is not in any group: it is set once and never changes.
BASIC_FIELDS = (
    "name", "description", "image", "cuisine", "country", "difficulty", "servings",
    "prep_minutes", "cook_minutes", "fridge_days", "freezer_months", "storage", "reheat",
)
LIST_FIELDS = ("tags", "equipment", "ingredients", "steps", "tips")
NUTRITION_FIELDS = ("calories", "protein_g", "carbs_g", "fat_g", "fiber_g")


def _non_negative_int(data: dict, key: str, default: int) -> int:
    value = int(data.get(key, default))
    if value < 0:
        raise ValueError(f"{key} must be >= 0, got {value}")
    return value


@dataclass(frozen=True)
class Nutrition:
    """Approximate nutrition for ONE serving."""

    calories: int
    protein_g: int
    carbs_g: int
    fat_g: int
    fiber_g: int = 0

    REQUIRED = ("calories", "protein_g", "carbs_g", "fat_g")

    @classmethod
    def from_dict(cls, data: dict) -> "Nutrition":
        missing = [key for key in cls.REQUIRED if key not in data]
        if missing:
            raise ValueError(f"nutrition is missing {', '.join(missing)}")
        return cls(**{key: _non_negative_int(data, key, 0) for key in NUTRITION_FIELDS})

    @property
    def macro_calories(self) -> int:
        """Calories implied by the macros (4 kcal/g protein & carbs, 9 kcal/g fat)."""
        return 4 * self.protein_g + 4 * self.carbs_g + 9 * self.fat_g


@dataclass(frozen=True)
class Recipe:
    id: str
    name: str
    ingredients: tuple[str, ...]
    steps: tuple[str, ...] = ()
    description: str = ""
    servings: int = 4
    prep_minutes: int = 0
    cook_minutes: int = 0
    fridge_days: int = 4
    tags: tuple[str, ...] = field(default_factory=tuple)
    cuisine: str = ""
    country: str = ""                 # optional; see countries.py
    difficulty: str = "easy"
    nutrition: Nutrition | None = None
    equipment: tuple[str, ...] = ()
    storage: str = ""
    reheat: str = ""
    freezer_months: int = 0           # 0 = don't freeze
    tips: tuple[str, ...] = ()
    image: str = ""                   # photo path under static/ (or a full URL)

    @property
    def total_minutes(self) -> int:
        return self.prep_minutes + self.cook_minutes

    @property
    def freezer_friendly(self) -> bool:
        return self.freezer_months > 0

    @classmethod
    def from_dict(cls, data: dict) -> "Recipe":
        if not data.get("id") or not data.get("name") or not data.get("ingredients"):
            raise ValueError(f"Recipe needs id, name and ingredients: {data!r}")
        difficulty = data.get("difficulty", "easy")
        if difficulty not in DIFFICULTIES:
            raise ValueError(
                f"{data['id']}: difficulty must be one of {DIFFICULTIES}, got {difficulty!r}")
        servings = int(data.get("servings", 4))
        if servings < 1:
            raise ValueError(f"{data['id']}: servings must be >= 1, got {servings}")
        nutrition = data.get("nutrition")
        cuisine = (data.get("cuisine") or "").strip()
        country = (data.get("country") or "").strip()
        if country and NATIONAL_CUISINES.get(cuisine) == country:
            cuisine = ""  # "Italian" + "Italy" says the same thing twice; keep the country
        return cls(
            id=data["id"],
            name=data["name"],
            ingredients=tuple(data["ingredients"]),
            steps=tuple(data.get("steps", ())),
            description=data.get("description", ""),
            servings=servings,
            prep_minutes=_non_negative_int(data, "prep_minutes", 0),
            cook_minutes=_non_negative_int(data, "cook_minutes", 0),
            fridge_days=_non_negative_int(data, "fridge_days", 4),
            tags=tuple(data.get("tags", ())),
            cuisine=cuisine,
            country=country,
            difficulty=difficulty,
            nutrition=Nutrition.from_dict(nutrition) if nutrition else None,
            equipment=tuple(data.get("equipment", ())),
            storage=data.get("storage", ""),
            reheat=data.get("reheat", ""),
            freezer_months=_non_negative_int(data, "freezer_months", 0),
            tips=tuple(data.get("tips", ())),
            image=data.get("image", ""),
        )

    def to_dict(self) -> dict:
        data = asdict(self)
        data["total_minutes"] = self.total_minutes
        data["freezer_friendly"] = self.freezer_friendly
        return data


def load_recipes(path: str | Path = DEFAULT_DATA) -> list[Recipe]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    recipes = [Recipe.from_dict(item) for item in data]
    ids = [recipe.id for recipe in recipes]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate recipe ids in data file")
    return recipes

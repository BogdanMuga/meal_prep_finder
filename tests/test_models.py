import json

import pytest

from meal_prep_finder.models import Nutrition, Recipe, load_recipes

# The smallest recipe the loader accepts; each test adds only what it checks.
MINIMAL = {"id": "test-bowl", "name": "Test Bowl", "ingredients": ["1 cup rice"]}


def test_minimal_recipe_gets_defaults():
    recipe = Recipe.from_dict(MINIMAL)
    assert recipe.servings == 4
    assert recipe.difficulty == "easy"
    assert recipe.country == ""
    assert recipe.nutrition is None


@pytest.mark.parametrize("missing", ["id", "name", "ingredients"])
def test_required_fields(missing):
    data = {**MINIMAL, missing: ""}
    with pytest.raises(ValueError, match="needs id, name and ingredients"):
        Recipe.from_dict(data)


@pytest.mark.parametrize("field, value, message", [
    ("difficulty", "expert", "difficulty must be one of"),
    ("servings", 0, "servings must be >= 1"),
    ("prep_minutes", -5, "prep_minutes must be >= 0"),
])
def test_bad_values_are_rejected(field, value, message):
    with pytest.raises(ValueError, match=message):
        Recipe.from_dict({**MINIMAL, field: value})


@pytest.mark.parametrize("cuisine, country, kept_cuisine", [
    ("Italian", "Italy", ""),                 # says the same thing twice: dropped
    ("Cajun", "United States", "Cajun"),      # a regional style: kept
    ("Italian", "", "Italian"),               # no country to replace it: kept
])
def test_national_cuisine_is_dropped_only_when_it_repeats_the_country(cuisine, country, kept_cuisine):
    recipe = Recipe.from_dict({**MINIMAL, "cuisine": cuisine, "country": country})
    assert recipe.cuisine == kept_cuisine
    assert recipe.country == country


def test_total_time_and_freezer_friendly():
    recipe = Recipe.from_dict({**MINIMAL, "prep_minutes": 10, "cook_minutes": 25, "freezer_months": 3})
    assert recipe.total_minutes == 35
    assert recipe.freezer_friendly


def test_nutrition_needs_all_macros():
    with pytest.raises(ValueError, match="missing protein_g, carbs_g, fat_g"):
        Recipe.from_dict({**MINIMAL, "nutrition": {"calories": 400}})


def test_macro_calories():
    nutrition = Nutrition.from_dict({"calories": 500, "protein_g": 30, "carbs_g": 40, "fat_g": 20})
    assert nutrition.macro_calories == 4 * 30 + 4 * 40 + 9 * 20     # 460
    assert nutrition.fiber_g == 0


def test_bundled_recipes_load():
    recipes = load_recipes()
    assert len(recipes) == 42
    assert len({recipe.id for recipe in recipes}) == 42


def test_duplicate_ids_are_rejected(tmp_path):
    path = tmp_path / "recipes.json"
    path.write_text(json.dumps([MINIMAL, MINIMAL]), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate recipe ids"):
        load_recipes(path)

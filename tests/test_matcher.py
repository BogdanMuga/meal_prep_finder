import pytest

from meal_prep_finder.matcher import RecipeIndex, parse_query, term_score
from meal_prep_finder.models import Recipe

@pytest.fixture
def index():
    recipes = [
        Recipe(id="chicken-rice", name="Chicken Rice",
               ingredients=("2 chicken thighs", "1 cup rice", "1 tsp salt")),
        Recipe(id="veggie-rice", name="Veggie Rice",
               ingredients=("1 cup rice", "1 head broccoli", "2 carrots")),
        Recipe(id="chicken-soup", name="Chicken Soup",
               ingredients=("4 cups chicken broth", "2 carrots", "1 onion")),
        Recipe(id="peanut-noodles", name="Peanut Noodles",
               ingredients=("8 oz rice noodles", "3 tbsp peanut butter", "1 cup broccoli florets")),
    ]
    return RecipeIndex(recipes)


def found(index, query, mode="any"):
    """The ids of the recipes a search returns, best first."""
    return [r.recipe.id for r in index.search(query, mode=mode).results]

@pytest.mark.parametrize("text, include", [
    ("chicken, rice", ["chicken", "rice"]),
    ("chicken and rice", ["chicken", "rice"]),
    ("chicken & rice + broccoli", ["chicken", "rice", "broccoli"]),
    ("Chicken Thighs, chicken thighs", ["chicken thigh"]),
])
def test_parse_query_splits_into_terms(text, include):
    assert parse_query(text).include == include

@pytest.mark.parametrize("text, include, exclude", [
    ("chicken, -nuts", ["chicken"], ["nut"]),
    ("chicken, no dairy", ["chicken"], ["dairy"]),
    ("rice, without onion", ["rice"], ["onion"]),
    ("!peanuts", [], ["peanut"]),
    ("-chicken, chicken", [], ["chicken"]),      # exclusion wins
])
def test_parse_query_finds_exclusions(text, include, exclude):
    query = parse_query(text)
    assert query.include == include
    assert query.exclude == exclude

@pytest.mark.parametrize("text", ["", "   ", "  ,  ;  "])
def test_parse_query_of_nothing_is_empty(text):
    assert parse_query(text).is_empty

@pytest.mark.parametrize("term, ingredient, score", [
    ("chicken", "chicken", 1.0),            # exact
    ("chicken", "chicken thigh", 0.75),     # term inside ingredient
    ("chicken thigh", "chicken", 0.75),     # ingredient inside term
    ("egg", "eggplant", 0.0),               # whole words only
])
def test_term_score_levels(term, ingredient, score):
    assert term_score(term, ingredient) == score

@pytest.mark.parametrize("term, ingredient", [
    ("butter", "peanut butter"),
    ("rice", "cauliflower rice"),
    ("onion", "green onion"),
])
def test_false_friends_do_not_match(term, ingredient):
    assert term_score(term, ingredient) == 0.0

@pytest.mark.parametrize("term, ingredient", [
    ("butter", "peanut butter"),
    ("rice", "cauliflower rice"),
    ("onion", "green onion"),
])
def test_false_friends_do_not_match(term, ingredient):
    assert term_score(term, ingredient) == 0.0

def test_broth_does_not_count_when_searching_for_chicken():
    assert term_score("chicken", "chicken broth") == 0.0


def test_broth_counts_when_avoiding_chicken():
    assert term_score("chicken", "chicken broth", excluding=True) == 0.75

@pytest.mark.parametrize("term, ingredient, score", [
    ("nut", "almond", 1.0),
    ("dairy", "feta", 1.0),
    ("meat", "tofu", 0.0),
])
def test_category_words_match_their_members(term, ingredient, score):
    assert term_score(term, ingredient) == score

def test_search_finds_recipes_with_the_ingredient(index):
    assert found(index, "chicken") == ["chicken-rice"]

def test_search_ignores_false_friends(index):
    assert found(index, "rice") == ["chicken-rice", "veggie-rice"]

def test_mode_any_needs_one_term(index):
    assert found(index, "chicken, rice", mode="any") == ["chicken-rice", "veggie-rice"]

def test_mode_all_needs_every_term(index):
    assert found(index, "chicken, rice", mode="all") == ["chicken-rice"]

# both veggie-rice and peanut-noodles have broccoli, -nuts expands
# to peanut (the CATEGORIES rule), so the noodles are removed.
def test_excluded_category_removes_recipes(index):
    assert found(index, "broccoli, -nuts") == ["veggie-rice"]

def test_excluding_chicken_also_removes_chicken_broth(index):
    assert "chicken-soup" not in found(index, "carrot, -chicken")
    assert "chicken-soup" in found(index, "carrot")

def test_misspelled_term_is_corrected(index):
    response = index.search("brocoli")
    assert response.corrections == {"brocoli": "broccoli"}
    assert found(index, "brocoli") == ["peanut-noodles", "veggie-rice"]


def test_unknown_term_is_reported_not_guessed(index):
    response = index.search("dragonfruit")
    assert response.unknown_terms == ["dragonfruit"]
    assert response.results == []

def test_better_match_ranks_first(index):
    results = index.search("chicken, rice").results
    assert results[0].recipe.id == "chicken-rice"
    assert results[0].score > results[1].score
    assert results[0].missing_ingredients == []         # salt is a pantry staple
    assert results[1].missing_ingredients == ["1 head broccoli", "2 carrots"]
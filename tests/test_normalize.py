from meal_prep_finder.normalize import normalize_ingredient
import pytest

def test_lowercases_the_name():
    assert normalize_ingredient("Chicken") == "chicken"

def test_removes_quantities_and_units():
    assert normalize_ingredient("2 cups rice") == "rice"

def test_removes_preparation_words_and_text_after_comma():
    assert normalize_ingredient("1 lb chicken thighs, cut into cubes") == "chicken thigh"

def test_returns_empty_string_when_nothing_is_left():
    assert normalize_ingredient("") == ""
    assert normalize_ingredient("2 cups chopped") == ""

@pytest.mark.parametrize("text, expected", [
    # regular plurals
    ("carrots", "carrot"),
    ("eggs", "egg"),
    ("peas", "pea"),
    ("berries", "berry"),             # -ies  -> -y
    ("radishes", "radish"),           # -shes -> -sh
    ("peaches", "peach"),             # -ches -> -ch
    # irregular plurals (IRREGULAR_PLURALS table)
    ("tomatoes", "tomato"),
    ("potatoes", "potato"),
    ("leaves", "leaf"),
    ("chilies", "chili"),
    # only the last word changes
    ("brussels sprouts", "brussels sprout"),
    # words that only look plural (NOT_PLURAL set): unchanged
    ("oats", "oats"),
    ("hummus", "hummus"),
    ("asparagus", "asparagus"),
    ("couscous", "couscous"),
])
def test_singular_form(text, expected):
    assert normalize_ingredient(text) == expected

@pytest.mark.parametrize("text, expected", [
    ("Scallions", "green onion"),
    ("spring onions", "green onion"),
    ("garbanzo beans", "chickpea"),
    ("aubergine", "eggplant"),
    ("courgettes", "zucchini"),
    ("prawns", "shrimp"),
    ("rocket", "arugula"),
    ("yoghurt", "yogurt"),
    ("Greek yoghurt", "greek yogurt"),
])
def test_synonyms_map_to_one_name(text, expected):
    assert normalize_ingredient(text) == expected

@pytest.mark.parametrize("text, expected", [
    ("½ cup milk", "milk"),                          # unicode fraction
    ("Jalapeño", "jalapeno"),                        # accent removed
    ("Crème fraîche", "creme fraiche"),              # several accents
    ("1 (14 oz) can black beans", "black bean"),     # parentheses, unit, plural
    ("3 cloves garlic, minced", "garlic"),           # unit + comma
    ("1 cup cooked brown rice", "brown rice"),       # prep word in the middle
])
def test_real_recipe_lines(text, expected):
    assert normalize_ingredient(text) == expected

@pytest.mark.xfail(reason="'dried' is removed as a prep word, even inside 'sun-dried'")
def test_sun_dried_tomatoes_keep_their_name():
    assert normalize_ingredient("sun-dried tomatoes") == "sun-dried tomato"
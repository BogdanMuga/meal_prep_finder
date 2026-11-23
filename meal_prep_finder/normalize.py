"""Turn messy ingredient text into canonical ingredient names.

"2 1/2 cups finely chopped Red Onions (about 2)"  ->  "red onion"
"3 Scallions, sliced"                              ->  "green onion"
"""

from __future__ import annotations

import re
import unicodedata

# --- vocabulary ---------------------------------------------------------------

UNITS = {
    "cup", "cups", "c", "tablespoon", "tablespoons", "tbsp", "tbs", "teaspoon",
    "teaspoons", "tsp", "gram", "grams", "g", "kg", "kilogram", "kilograms",
    "ml", "l", "liter", "liters", "litre", "litres", "oz", "ounce", "ounces",
    "lb", "lbs", "pound", "pounds", "pinch", "pinches", "dash", "dashes",
    "clove", "cloves", "can", "cans", "jar", "jars", "package", "packages",
    "pack", "packs", "bunch", "bunches", "handful", "handfuls", "slice",
    "slices", "piece", "pieces", "head", "heads", "stalk", "stalks", "sprig",
    "sprigs", "block", "blocks", "fillet", "fillets", "bag", "bags", "scoop",
    "scoops", "sheet", "sheets",
}

# Words that describe preparation / size / state but not *what* the ingredient is.
DESCRIPTORS = {
    "chopped", "diced", "minced", "sliced", "grated", "shredded", "crushed",
    "cubed", "julienned", "peeled", "seeded", "trimmed", "halved", "quartered",
    "rinsed", "drained", "cooked", "uncooked", "raw", "fresh", "freshly",
    "frozen", "thawed", "dried", "large", "medium", "small", "extra", "finely",
    "roughly", "coarsely", "thinly", "thickly", "lightly", "boneless",
    "skinless", "lean", "ripe", "organic", "optional", "about", "approx",
    "approximately", "to", "taste", "of", "for", "serving", "garnish", "the",
    "a", "an", "and", "or", "plus", "more", "divided", "packed", "heaping",
    "level", "room", "temperature", "softened", "melted", "warm", "cold",
    "hot", "whole", "into", "cut", "inch", "cm", "bite", "sized", "size",
    "pieces", "low", "sodium", "reduced", "fat", "unsalted", "salted",
    "canned", "store", "bought", "homemade", "good", "quality", "pitted",
    "floret", "florets", "unsweetened", "sweetened", "natural", "crumbled",
    "plain", "toasted", "firm", "shelled", "baby", "mixed", "kernel",
    "kernels", "spiralized", "juiced", "zested", "deveined", "cored", "pressed",
}

# Plural forms that simple rules get wrong, and words that only *look* plural.
IRREGULAR_PLURALS = {
    "leaves": "leaf",
    "loaves": "loaf",
    "halves": "half",
    "knives": "knife",
    "potatoes": "potato",
    "tomatoes": "tomato",
    "mangoes": "mango",
    "chilies": "chili",
    "chillies": "chili",
    "chiles": "chili",
    "anchovies": "anchovy",
}
NOT_PLURAL = {
    "hummus", "couscous", "asparagus", "swiss", "molasses", "citrus",
    "lemongrass", "grass", "bass", "harissa",
    "oats",      # the ingredient is called "oats"
    "greens", "brussels", "grits",
}

# Different names for the same thing -> one canonical name.
SYNONYMS = {
    "scallion": "green onion",
    "spring onion": "green onion",
    "garbanzo bean": "chickpea",
    "garbanzo": "chickpea",
    "coriander leaf": "cilantro",
    "aubergine": "eggplant",
    "courgette": "zucchini",
    "capsicum": "bell pepper",
    "sweet pepper": "bell pepper",
    "prawn": "shrimp",
    "minced beef": "ground beef",
    "beef mince": "ground beef",
    "minced turkey": "ground turkey",
    "turkey mince": "ground turkey",
    "rocket": "arugula",
    "chilli": "chili",
    "chile": "chili",
    "yoghurt": "yogurt",
    "greek yoghurt": "greek yogurt",
    "corn flour": "cornstarch",
    "rolled oats": "oats",
    "old fashioned oats": "oats",
    "tamari": "soy sauce",
    "bok choi": "bok choy",
    "pak choi": "bok choy",
    "chick pea": "chickpea",
}

_UNICODE_FRACTIONS = "¼½¾⅐⅑⅒⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞"
_NUMBER_RE = re.compile(r"\d+([./]\d+)?|[" + _UNICODE_FRACTIONS + "]")
_PAREN_RE = re.compile(r"\([^)]*\)")
_NON_WORD_RE = re.compile(r"[^a-z\s-]")


# --- helpers -----------------------------------------------------------------

def singularize(word: str) -> str:
    """Very small English singularizer tuned for ingredient names."""
    if word in NOT_PLURAL or len(word) <= 3:
        return word
    if word in IRREGULAR_PLURALS:
        return IRREGULAR_PLURALS[word]
    if word.endswith("ies"):
        return word[:-3] + "y"           # berries -> berry
    if word.endswith(("ches", "shes", "sses", "xes", "zes")):
        return word[:-2]                  # radishes -> radish
    if word.endswith("oes"):
        return word[:-2]                  # (fallback) -> tomato
    if word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]                  # carrots -> carrot
    return word


def _strip_accents(text: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char)
    )


def apply_synonyms(name: str) -> str:
    """Replace the longest synonym phrase found in `name`."""
    if name in SYNONYMS:
        return SYNONYMS[name]
    # phrase-level replacement inside a longer name, longest synonyms first
    for alias in sorted(SYNONYMS, key=len, reverse=True):
        pattern = rf"\b{re.escape(alias)}\b"
        if re.search(pattern, name):
            return re.sub(pattern, SYNONYMS[alias], name)
    return name


# --- public API ----------------------------------------------------------------

def normalize_ingredient(text: str) -> str:
    """Return a canonical ingredient name (may be '' if nothing meaningful remains)."""
    if not text:
        return ""
    text = _strip_accents(text.lower())
    text = text.split(",")[0]            # "onion, finely chopped" -> "onion"
    text = _PAREN_RE.sub(" ", text)       # drop "(about 2)"
    text = _NUMBER_RE.sub(" ", text)      # drop quantities
    text = text.replace("-", " ")
    text = _NON_WORD_RE.sub(" ", text)

    words = [word for word in text.split() if word not in UNITS and word not in DESCRIPTORS]
    words = [singularize(word) for word in words]
    name = " ".join(words).strip()
    return apply_synonyms(name)


def tokens(name: str) -> list[str]:
    return name.split()

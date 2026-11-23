"""Ingredient matching and recipe ranking.

How a search works
------------------
1. The query text is parsed into "include" and "exclude" terms
   ("chicken, rice, -peanuts" -> include [chicken, rice], exclude [peanut]).
2. Every term is normalized the same way recipe ingredients are, so
   "Cherry Tomatoes" and "1 cup cherry tomatoes, halved" both become "cherry tomato".
3. Terms that match nothing are spell-corrected against the known vocabulary
   ("brocoli" -> "broccoli"). Category words ("nut", "dairy", "seafood") expand
   to their members.
   Exclusions are stricter than inclusions: "-chicken" also removes recipes
   with chicken broth, but searching "chicken" won't return them.
4. Each term is scored against each recipe ingredient:
      1.0   exact canonical match          chicken thigh  == chicken thigh
      0.75  whole-word containment         chicken        in chicken thigh
      0.0   no match, or a known false friend (butter vs peanut butter)
5. Recipes are filtered (mode "all"/"any", exclusions) and ranked by how well
   they cover the query and how much of the recipe the user already has.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Iterable, Literal

from .models import Recipe
from .countries import slugify
from .normalize import normalize_ingredient, tokens

EXACT = 1.0
PARTIAL = 0.75

# A recipe's score: how well it covers the query (70%) and how much of the
# recipe the user already has (30%).
QUERY_WEIGHT = 0.7
RECIPE_WEIGHT = 0.3

# "X" should NOT match these compound ingredients even though the words overlap.
FALSE_FRIENDS: dict[str, set[str]] = {
    "butter": {"peanut butter", "almond butter", "cashew butter", "apple butter"},
    "milk": {"coconut milk", "almond milk", "oat milk", "soy milk"},
    "cream": {"cream cheese", "coconut cream"},
    "rice": {"rice vinegar", "rice paper", "rice noodle", "cauliflower rice"},
    "onion": {"green onion"},
    "potato": {"sweet potato"},
    "egg": {"egg noodle"},
}

# Not a kind of X, but *made from* X. Ignored when searching for X to cook with,
# but still counts when the user wants to AVOID X (vegetarians and broth).
DERIVED_FROM: dict[str, set[str]] = {
    "chicken": {"chicken broth", "chicken stock"},
    "beef": {"beef broth", "beef stock"},
    "fish": {"fish sauce"},
}

# Category words that expand to concrete ingredients.
CATEGORIES: dict[str, set[str]] = {
    "nut": {"almond", "cashew", "peanut", "walnut", "pecan", "pistachio",
            "hazelnut", "pine nut"},
    "dairy": {"milk", "cheese", "butter", "yogurt", "cream", "feta", "parmesan",
              "mozzarella", "cheddar", "ricotta"},
    "seafood": {"shrimp", "salmon", "tuna", "cod", "tilapia", "fish", "crab"},
    "fish": {"salmon", "tuna", "cod", "tilapia", "fish"},
    "meat": {"chicken", "beef", "pork", "turkey", "lamb", "bacon", "sausage"},
}

# Ignored when listing what the user still needs to buy.
PANTRY_STAPLES = {
    "salt", "black pepper", "pepper", "water", "olive oil", "oil",
    "vegetable oil", "cooking spray", "sea salt", "kosher salt",
}

_SPLIT_RE = re.compile(r"[,;\n]+|\s+and\s+|\s*&\s*|\s*\+\s*")
_EXCLUDE_PREFIX_RE = re.compile(r"^(?:-|!|no\s+|without\s+|not\s+)\s*")

Mode = Literal["any", "all"]


# --- query parsing -------------------------------------------------------------

@dataclass
class ParsedQuery:
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.include and not self.exclude


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: dict[str, None] = {}
    for item in items:
        if item and item not in seen:
            seen[item] = None
    return list(seen)


def parse_query(text: str) -> ParsedQuery:
    """Split free text into normalized include / exclude terms."""
    include, exclude = [], []
    for raw in _SPLIT_RE.split(text or ""):
        raw = raw.strip().lower()
        if not raw:
            continue
        prefix = _EXCLUDE_PREFIX_RE.match(raw)
        target = exclude if prefix else include
        target.append(normalize_ingredient(raw[prefix.end():] if prefix else raw))
    exclude = _dedupe(exclude)
    include = [term for term in _dedupe(include) if term not in exclude]
    return ParsedQuery(include=include, exclude=exclude)


# --- single term vs single ingredient ---------------------------------------

def _contains_phrase(haystack: list[str], needle: list[str]) -> bool:
    """True if `needle` appears as consecutive whole words inside `haystack`."""
    size = len(needle)
    return any(haystack[i:i + size] == needle for i in range(len(haystack) - size + 1))


def term_score(term: str, ingredient: str, excluding: bool = False) -> float:
    """Score how well a canonical query term matches a canonical ingredient.

    `excluding=True` is used for "-term" filters: there, products *derived*
    from the term (chicken broth for "chicken") also count as a match.
    """
    if not term or not ingredient:
        return 0.0
    if term in CATEGORIES:
        # members are matched literally (no further expansion), so a category
        # may list a word that is itself a category ("seafood" -> "fish")
        return max(
            (_literal_score(member, ingredient, excluding) for member in CATEGORIES[term]),
            default=0.0,
        )
    return _literal_score(term, ingredient, excluding)


def _literal_score(term: str, ingredient: str, excluding: bool) -> float:
    if term == ingredient:
        return EXACT
    term_words, ingredient_words = tokens(term), tokens(ingredient)
    if (_is_false_friend(term_words, ingredient_words, excluding)
            or _is_false_friend(ingredient_words, term_words, excluding)):
        return 0.0
    if (_contains_phrase(ingredient_words, term_words)
            or _contains_phrase(term_words, ingredient_words)):
        return PARTIAL
    return 0.0


def _is_false_friend(short: list[str], long: list[str], excluding: bool = False) -> bool:
    """True if `long` contains a compound that merely looks like `short`.

    e.g. short=["butter"], long=["peanut", "butter"] -> True
    """
    key = " ".join(short)
    compounds = set(FALSE_FRIENDS.get(key, ()))
    if not excluding:
        compounds |= DERIVED_FROM.get(key, set())
    return any(_contains_phrase(long, tokens(compound)) for compound in compounds)


# --- results -------------------------------------------------------------------

@dataclass
class IngredientMatch:
    term: str
    ingredient: str       # the recipe's original line
    canonical: str
    score: float


@dataclass
class SearchResult:
    recipe: Recipe
    score: float
    matches: list[IngredientMatch]
    missing_terms: list[str]          # query terms this recipe doesn't use
    missing_ingredients: list[str]    # recipe lines the user didn't mention (minus staples)

    def to_dict(self) -> dict:
        return {
            "recipe": self.recipe.to_dict(),
            "score": self.score,
            "matches": [match.__dict__ for match in self.matches],
            "missing_terms": self.missing_terms,
            "missing_ingredients": self.missing_ingredients,
        }


@dataclass
class SearchResponse:
    query: ParsedQuery
    mode: Mode
    results: list[SearchResult]
    corrections: dict[str, str]       # "brocoli" -> "broccoli"
    unknown_terms: list[str]          # terms we couldn't match or correct

    def to_dict(self) -> dict:
        return {
            "include": self.query.include,
            "exclude": self.query.exclude,
            "mode": self.mode,
            "corrections": self.corrections,
            "unknown_terms": self.unknown_terms,
            "count": len(self.results),
            "results": [result.to_dict() for result in self.results],
        }


# --- the index -----------------------------------------------------------------

class RecipeIndex:
    """Holds recipes with pre-normalized ingredients and answers searches."""

    def __init__(self, recipes: Iterable[Recipe], fuzzy_cutoff: float = 0.8):
        self.recipes: list[Recipe] = list(recipes)
        self.fuzzy_cutoff = fuzzy_cutoff
        self._canonical: dict[str, list[tuple[str, str]]] = {
            recipe.id: [(line, normalize_ingredient(line)) for line in recipe.ingredients]
            for recipe in self.recipes
        }
        known_words: set[str] = set(CATEGORIES)
        for pairs in self._canonical.values():
            for _, canon in pairs:
                if canon:
                    known_words.add(canon)
                    known_words.update(tokens(canon))
        self.vocabulary = sorted(known_words)

    # -- countries --

    def countries(self) -> list[tuple[str, int]]:
        """(country, recipe count) for every country used, alphabetically."""
        counts: dict[str, int] = {}
        for recipe in self.recipes:
            if recipe.country:
                counts[recipe.country] = counts.get(recipe.country, 0) + 1
        return sorted(counts.items())

    def by_country(self, country: str) -> list[Recipe]:
        """Recipes from `country`, matched by name or slug, case-insensitively."""
        wanted = slugify(country)
        return sorted((recipe for recipe in self.recipes
                       if recipe.country and slugify(recipe.country) == wanted),
                      key=lambda recipe: recipe.name)

    # -- term resolution --

    def _is_known(self, term: str) -> bool:
        return any(term_score(term, word) > 0 for word in self.vocabulary)

    def resolve_term(self, term: str) -> str | None:
        """Return the term itself, a spelling correction, or None if hopeless."""
        if self._is_known(term):
            return term
        close = difflib.get_close_matches(term, self.vocabulary, n=1, cutoff=self.fuzzy_cutoff)
        return close[0] if close else None

    # -- scoring --

    def _best_match(self, term: str, recipe: Recipe) -> IngredientMatch | None:
        best: IngredientMatch | None = None
        for line, canon in self._canonical[recipe.id]:
            score = term_score(term, canon)
            if score > 0 and (best is None or score > best.score):
                best = IngredientMatch(term=term, ingredient=line, canonical=canon, score=score)
        return best

    def _contains_any(self, recipe: Recipe, terms: list[str]) -> bool:
        return any(
            term_score(term, canon, excluding=True) > 0
            for term in terms
            for _, canon in self._canonical[recipe.id]
        )

    # -- public --

    def search(
        self,
        query: str | ParsedQuery,
        mode: Mode = "any",
        limit: int | None = None,
    ) -> SearchResponse:
        if mode not in ("any", "all"):
            raise ValueError(f"mode must be 'any' or 'all', got {mode!r}")
        parsed = parse_query(query) if isinstance(query, str) else query

        corrections: dict[str, str] = {}
        unknown: list[str] = []

        def resolve_all(terms: list[str]) -> list[str]:
            resolved_terms = []
            for term in terms:
                resolved = self.resolve_term(term)
                if resolved is None:
                    unknown.append(term)
                    continue
                if resolved != term:
                    corrections[term] = resolved
                resolved_terms.append(resolved)
            return _dedupe(resolved_terms)

        include = resolve_all(parsed.include)
        exclude = resolve_all(parsed.exclude)
        resolved_query = ParsedQuery(include=include, exclude=exclude)

        results: list[SearchResult] = []
        for recipe in self.recipes:
            if exclude and self._contains_any(recipe, exclude):
                continue

            matches = [match for term in include if (match := self._best_match(term, recipe))]
            matched_terms = {match.term for match in matches}
            missing_terms = [term for term in include if term not in matched_terms]

            if include:
                if mode == "all" and missing_terms:
                    continue
                if mode == "any" and not matches:
                    continue
            elif not exclude:
                continue  # empty query -> no results

            results.append(self._build_result(recipe, include, matches, missing_terms))

        results.sort(key=lambda result: (-result.score, len(result.missing_ingredients),
                                         result.recipe.name))
        if limit is not None:
            results = results[:limit]
        return SearchResponse(resolved_query, mode, results, corrections, unknown)

    def _build_result(self, recipe, include, matches, missing_terms) -> SearchResult:
        needed = [
            (line, canon) for line, canon in self._canonical[recipe.id]
            if canon and canon not in PANTRY_STAPLES
        ]
        covered = [
            (line, canon) for line, canon in needed
            if any(term_score(term, canon) > 0 for term in include)
        ]
        query_coverage = (sum(match.score for match in matches) / len(include)) if include else 1.0
        recipe_coverage = (len(covered) / len(needed)) if needed else 1.0
        score = round(QUERY_WEIGHT * query_coverage + RECIPE_WEIGHT * recipe_coverage, 4)
        missing_ingredients = [line for line, canon in needed if (line, canon) not in covered]
        return SearchResult(recipe, score, matches, missing_terms, missing_ingredients)

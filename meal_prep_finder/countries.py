"""Country names used by recipes, plus helpers for URL slugs and flag emoji.

A recipe's origin is stated once:

- ``country`` for dishes from one country ("Italy", not cuisine "Italian");
- ``cuisine`` only for a regional style that isn't a single country
  ("Cajun", "Tex-Mex", "Mediterranean"); it can sit alongside a country;
- neither for generic dishes (overnight oats, parfaits, ...).
"""

from __future__ import annotations

import re

# Display name -> ISO 3166-1 alpha-2 code (used only to build the flag emoji).
COUNTRY_CODES: dict[str, str] = {
    "China": "CN",
    "France": "FR",
    "Greece": "GR",
    "India": "IN",
    "Italy": "IT",
    "Japan": "JP",
    "Lebanon": "LB",
    "Mexico": "MX",
    "Morocco": "MA",
    "South Korea": "KR",
    "Spain": "ES",
    "Thailand": "TH",
    "Turkey": "TR",
    "United Kingdom": "GB",
    "United States": "US",
    "Vietnam": "VN",
}


def slugify(text: str) -> str:
    """Make a URL name: 'South Korea' -> 'south-korea', 'Lemon Chicken Bowls' -> 'lemon-chicken-bowls'.

    Used for country pages and for new recipe ids."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def country_flag(name: str) -> str:
    """Flag emoji for a known country, or a globe for anything else."""
    code = COUNTRY_CODES.get(name)
    if not code:
        return "🌍"
    return "".join(chr(0x1F1E6 + ord(letter) - ord("A")) for letter in code)


# National cuisine labels. They only repeat the country: the loader drops one
# when the recipe has the matching country (Recipe.from_dict), and the bundled
# data must not use them at all (the editor rejects them).
NATIONAL_CUISINES: dict[str, str] = {
    "American": "United States",
    "Chinese": "China",
    "French": "France",
    "Greek": "Greece",
    "Indian": "India",
    "Italian": "Italy",
    "Japanese": "Japan",
    "Korean": "South Korea",
    "Lebanese": "Lebanon",
    "Mexican": "Mexico",
    "Moroccan": "Morocco",
    "Spanish": "Spain",
    "Thai": "Thailand",
    "Turkish": "Turkey",
    "British": "United Kingdom",
    "Vietnamese": "Vietnam",
}

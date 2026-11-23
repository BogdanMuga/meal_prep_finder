# Meal Prep Finder

Find meal-prep recipes using the ingredients you already have.

Type what's in your fridge, like `chicken, rice, broccoli`, and get recipes ranked by how well they match, with a list of what you still need to buy.

> **Note:** This is an educational project, made for learning purposes only.

## Download

Download the Windows app from [Releases](https://github.com/BogdanMuga/meal_prep_finder/releases/latest).

> **Tip:** Best enjoyed on a full stomach. Running this app while hungry may cause uncontrollable cravings.

## Features

- **Search by ingredient.** Separate ingredients with commas. Put `-` or `no` in front of anything to leave it out (`-nuts`, `no dairy`). Choose **Any** to match at least one ingredient, or **All** to match every one.
- **Forgiving search.** It fixes typos ("brocoli" → "broccoli"), knows other names for the same food ("scallion" = "green onion"), and ignores amounts and plurals.
- **Useful results.** Each recipe shows its match %, the ingredients you have, what's missing, cooking time, servings, calories and protein, how long it keeps, and the full recipe.
- **Browse.** By country of origin (with **General** for everyday dishes), or all recipes A to Z.
- **Recipe editor (optional).** Add, edit and delete recipes, and upload photos.
- **Private.** Everything runs on your own PC.

## Run it from the project

To run it from the code instead, you need Python 3.10 or newer. Run these in the project folder.

**Windows** (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .
python run_app.py
```

**macOS / Linux** (Terminal):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python run_app.py
```

Your browser opens at http://127.0.0.1:5000. To stop the app, close the window or press `Ctrl+C`.

To turn on the recipe editor, start it with `python run_app.py --admin`. The editor has no login, so only use it on your own PC.

To build the Windows app yourself, run `build.bat`. It creates a `bin` folder with `MealPrepFinder.exe`.

## Your recipes

The app starts with 42 recipes: dishes from 11 countries and a few everyday ones.

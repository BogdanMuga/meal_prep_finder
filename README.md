# Meal Prep Finder

Tell it what food you have, and it finds meal-prep recipes you can make with it. Made with Python, Flask and SQLite.

```
chicken, brocoli, rice, -nuts   →   Teriyaki Chicken Rice Bowls (66%), Sheet-Pan Lemon Chicken & Veggies (49%), …
```

It fixes the spelling ("brocoli" becomes "broccoli"), and `-nuts` means "no nuts".

## Start it

Run these in the project folder. The commands are a little different on Windows and on macOS/Linux.

**Windows** (PowerShell):

```powershell
# 1. Create a virtual environment (a private Python just for this project)
python -m venv .venv
# 2. Turn it on (do this every time you open a new terminal)
.venv\Scripts\activate
# 3. Install the app and its libraries
pip install -e .
# 4. Start the app
python -m flask --app meal_prep_finder.app:create_app run --debug
```

**macOS / Linux** (Terminal):

```bash
# 1. Create a virtual environment (a private Python just for this project)
python3 -m venv .venv
# 2. Turn it on (do this every time you open a new terminal)
source .venv/bin/activate
# 3. Install the app and its libraries
pip install -e .
# 4. Start the app
python -m flask --app meal_prep_finder.app:create_app run --debug
```

Then open http://127.0.0.1:5000 in your browser. There are two tabs:

- **Search by ingredient** (`/`): type what's in your fridge.
- **Browse**, which has two views:
  - **By origin** (`/countries`): one tile for each country, such as `/countries/italy`. The first tile, **General** (`/countries/general`), holds the recipes that don't come from one country.
  - **All recipes** (`/recipes`): every recipe, A to Z.

## Use it on a PC without Python (Windows only)

This part only works on Windows: it makes a Windows `.exe`. On a Windows PC where the steps above already work, run this in the project folder:

```bat
build.bat
```

This makes the `bin\` folder, which is the finished app. It holds `MealPrepFinder.exe` and an `_internal\` folder with everything the exe needs: libraries, pages, photos and the database. Copy the whole `bin` folder to the other PC, for example as a zip. That PC needs 64-bit Windows 10 or 11, but no Python.

| Command | What it does |
|---|---|
| `MealPrepFinder.exe` | Starts the app at http://127.0.0.1:5000 and opens your browser |
| `MealPrepFinder.exe --admin` | The same, with the recipe editor turned on |
| `MealPrepFinder.exe --port 8080` | Uses a different port, if 5000 is already in use |

To stop the app, close its console window.

- **Your data:** the recipes are saved in `_internal\data\recipes.db`. The first time the app runs, it creates this file and fills it with the recipes that come with the app. Photos you upload go to `_internal\meal_prep_finder\static\recipes\`. Running `build.bat` again updates the app but keeps your recipes and photos. To back up your changes, copy those two.
- **Windows warning:** the first time, Windows SmartScreen may warn you because the app isn't signed. Click "More info", then "Run anyway".
- **Only on this PC:** the app only accepts connections from the PC it runs on (`127.0.0.1`). Phones and other computers can't open it, and Windows Firewall won't ask about it.

You can also start the app this way from the project, without building. It works on every system, with the virtual environment turned on:

```bash
python run_app.py            # search and browse
python run_app.py --admin    # also turn on the recipe editor
```

## Where the recipes are saved

Recipes are saved in `data/recipes.db` in the project folder, a SQLite database. It's a single file, with no database server to install. The first time the app starts, it creates this file and fills it from `meal_prep_finder/data/recipes.json`. From then on, the database holds your current recipes and `recipes.json` is the backup.

Every way of running the app from the project uses this same file: `python -m flask ... run`, `python run_app.py` and the commands below. So a recipe you add in one shows up in the others, and `export-recipes` saves it. The built `MealPrepFinder.exe` is the only exception: it keeps its own copy in `bin\_internal\data\recipes.db`, so it works on a PC without the project.

Run these commands in the project folder, with the virtual environment turned on (see [Start it](#start-it)). They're the same on Windows, macOS and Linux.

| Command | What it does |
|---|---|
| `python -m flask --app meal_prep_finder.app:create_app init-db` | Creates the database if it doesn't exist yet, and says how many recipes it has |
| `python -m flask --app meal_prep_finder.app:create_app init-db --reset` | Deletes every recipe in the database and loads `recipes.json` again. It asks you first |
| `python -m flask --app meal_prep_finder.app:create_app export-recipes` | Saves the database back into `recipes.json`. Do this to keep changes you made in the editor |
| `python -m flask --app meal_prep_finder.app:create_app db migrate -m "…"`, then `python -m flask --app meal_prep_finder.app:create_app db upgrade` | After you change the recipe table in `db.py`, these record the change and apply it to the database (Flask-Migrate and Alembic). The app also applies recorded changes by itself when it starts |

To use a different database, set `MEAL_PREP_DATABASE_URL` to its address (any SQLAlchemy database URL) before starting the app.

**Windows** (PowerShell):

```powershell
# Use another database file for this terminal
$env:MEAL_PREP_DATABASE_URL = "sqlite:///C:/path/to/other.db"
python -m flask --app meal_prep_finder.app:create_app run --debug
```

**macOS / Linux** (Terminal):

```bash
# Use another database file for this terminal
export MEAL_PREP_DATABASE_URL="sqlite:////path/to/other.db"
python -m flask --app meal_prep_finder.app:create_app run --debug
```

## Edit recipes in the app

The recipe editor is off unless you turn it on. To turn it on, start the app with `ADMIN_ENABLED=1`:

**Windows** (PowerShell):

```powershell
# Turn the editor on for this terminal, then start the app
$env:ADMIN_ENABLED = "1"
python -m flask --app meal_prep_finder.app:create_app run --debug
# To turn it off again in the same terminal:
Remove-Item Env:ADMIN_ENABLED
```

**macOS / Linux** (Terminal):

```bash
# Turn the editor on for this one start of the app
ADMIN_ENABLED=1 python -m flask --app meal_prep_finder.app:create_app run --debug
```

If you use Git Bash on Windows, the macOS / Linux line above works there too.

You then get a third tab, **✏️ Manage recipes** (`/admin/`). It lists every recipe with Edit and Delete buttons, and every recipe card gets an Edit link.

- **Adding or editing:**
  - Put one item per line for ingredients, steps, equipment and tips, and separate tags with commas.
  - The ID is the recipe's name in web addresses, like `lemon-chicken-bowls`. If you leave it empty, it's made from the recipe's name. You can't change it later.
- **What it checks:**
  - Each recipe needs its own ID and name, and a difficulty of easy, medium or hard.
  - If you fill in nutrition, give calories, protein, carbs and fat. The calories must be within 5% of what the protein, carbs and fat add up to.
  - Use the `freezer-friendly` tag only when the recipe can be frozen.
  - Pick a country instead of typing a cuisine word like "Italian".
  - If something is wrong, the form comes back with your text kept and a note saying what to fix.
- **Photos:** upload a JPEG, PNG or WebP picture. The app checks that the file really is a picture, not just that its name ends in `.jpg`. It saves the photo as `static/recipes/<id>.jpg` (700 pixels wide), plus a small copy 350 pixels wide. Uploading again replaces the photo. Tick "Remove the current photo" to delete it.
- **Deleting** asks you first, and also removes the recipe's photos.
- **Changes show up straight away** in search, on the Browse pages and in the API.

The editor has no login, so only use it on your own PC. Every form carries a hidden security token (CSRF protection), so other websites can't send changes to it. Don't turn the editor on for a copy that other people can open.

## How the search works

| Step | What happens | Example |
|---|---|---|
| **Split** | Your text is split at `,` `;` `and` `&` `+` and new lines. A word that starts with `-`, `!`, `no `, `without ` or `not ` means "leave this out". | `chicken and rice, no dairy` → use `chicken` and `rice`, leave out `dairy` |
| **Clean up** | Makes the text lowercase and removes accents, amounts, units, anything in brackets, cooking words ("chopped", "boneless") and everything after a comma. Then it makes the word singular. | `2 lbs boneless skinless Chicken Thighs, cubed` → `chicken thigh` |
| **Other names** | Different names for the same food become one name. | scallion → green onion, garbanzo → chickpea, aubergine → eggplant, prawn → shrimp |
| **Fix spelling** | A word that matches nothing is compared with the words used in the recipes (with Python's `difflib`, which needs them to be at least 80% alike). If nothing is close enough, the word is listed as unknown instead of guessed. | `brocoli` → `broccoli`, `dragonfruit` → unknown |
| **Group words** | Some words stand for a whole group of foods. | `nut`, `dairy`, `meat`, `seafood`, `fish` |
| **Score a word** | The same name scores 1.0. If one name contains the other as whole words, it scores 0.75. | `chicken` and `chicken thigh` score 0.75, `egg` and `eggplant` score 0 |
| **Look-alikes** | Names that share a word but are a different food don't match. | `butter` ≠ `peanut butter`, `milk` ≠ `coconut milk`, `rice` ≠ `rice vinegar` or `cauliflower rice`, `onion` ≠ `green onion` |
| **Made from it** | Things made from a food, like chicken broth, don't count when you search *for* that food, but do count when you leave it *out*. | `chicken` won't find a soup that only has chicken broth, but `-meat` removes that soup |
| **Filter** | With `mode=any` (the default), at least one of your words must match. With `mode=all`, every word must match. A recipe that has anything you left out is dropped. | |
| **Sort** | Score = 70% "how many of your words the recipe uses" + 30% "how much of the recipe you already have". Basics like salt and oil don't count. When two scores are equal, the recipe with fewer missing ingredients comes first. | |

Each result shows how it was found: which recipe line matched each of your words, which of your words it doesn't use, and what you still need to buy.

## JSON API

For other programs that want the data. Every answer is JSON.

| Address | What you get |
|---|---|
| `GET /api/search?q=chicken,rice&mode=all&limit=5` | A search. `mode` is `any` (the default) or `all`. `limit` is how many results you want, from 1 to 100. |
| `GET /api/recipes` | All recipes. Add `?country=Italy` to get one country's recipes. The country can be written as its name or its URL form, in upper or lower case. |
| `GET /api/countries` | The countries that have recipes, each with its URL form, flag and number of recipes |
| `GET /api/recipes/<id>` | One recipe, or a 404 error if no recipe has that ID |

## What's in the project

```
meal_prep_finder/
  normalize.py     turns ingredient text into a simple name ("2 cups Red Onions, sliced" → "red onion")
  matcher.py       reads the search, scores each ingredient and ranks the recipes (RecipeIndex.search)
  models.py        what a recipe looks like (Recipe, Nutrition), its checks, and reading recipes.json
  countries.py     country names, URL names and flags
  app.py           the Flask app: pages, JSON API, database setup, and the init-db / export-recipes commands
  db.py            the database table (SQLAlchemy), and writing recipes.json
  editor.py        the recipe editor (at /admin): forms, checks and photo upload (Pillow)
  migrations/      the history of changes to the database table (Alembic, through Flask-Migrate)
  data/recipes.json   42 meal-prep recipes: 32 from 11 countries and 10 general ones
  static/recipes/  dish photos: <id>.jpg (about 700 px wide) and <id>-small.jpg (a small copy)
  templates/       the HTML pages: base.html (layout and tabs), _card.html (one recipe card),
                   index.html (search), browse.html, and editor/ (list, form and delete pages)
```

## Adding to it

- **Add recipes:** use the editor, then run `export-recipes` to save them into `recipes.json`. Or edit `data/recipes.json` by hand (see the format below), then run `init-db --reset` to load it.
- **Teach it another name for a food, or a new look-alike:** add it to `SYNONYMS` in `normalize.py`, or to `FALSE_FRIENDS`, `DERIVED_FROM` or `CATEGORIES` in `matcher.py`.

## Recipe format

Each recipe in `data/recipes.json` can have these fields. Only `id`, `name` and `ingredients` are required.

| Field | Example | Notes |
|---|---|---|
| `id`, `name`, `description` | `"lamb-kofta-couscous"` | `id` is the recipe's name in web addresses: lowercase words joined by dashes |
| `country` | `"Lebanon"` | Optional. Only set it when the dish clearly comes from one country. Use a name from `COUNTRY_CODES` in `countries.py`, and add new countries there. |
| `cuisine` | `"Tex-Mex"` | Optional. Only for a regional style that isn't one country (`Cajun`, `Tex-Mex`, `Mediterranean`). A recipe can have this and a country. Never use a national word like `"Italian"`; set `country` instead. Everyday dishes (oats, parfaits, …) have neither. |
| `image` | `"recipes/lamb-kofta-couscous.jpg"` | Optional photo of the dish, as a path inside `meal_prep_finder/static/`. Put a `<name>-small.jpg` copy (about 350 px wide) next to it for the photo strip and the Browse tiles; without one, the big photo is used. A full `https://` web address also works, but the recipes that come with the app use local files. |
| `difficulty` | `"medium"` | `easy`, `medium` or `hard` |
| `servings`, `prep_minutes`, `cook_minutes` | `4`, `20`, `15` | The total time is prep plus cook, worked out for you |
| `fridge_days`, `freezer_months` | `4`, `3` | `freezer_months: 0` means don't freeze it |
| `nutrition` | `{"calories": 515, "protein_g": 30, "carbs_g": 45, "fat_g": 24, "fiber_g": 4}` | For one serving. The editor checks that calories are within 5% of 4 × protein + 4 × carbs + 9 × fat. |
| `tags` | `["high-protein", "freezer-friendly"]` | Short labels. Use them to mean: `vegan` = no meat, fish, dairy, egg or honey; `gluten-free` = no wheat, pasta, soy sauce, …; `high-protein` = at least 25 g of protein; `low-carb` = at most 20 g of carbs; `freezer-friendly` = can be frozen (`freezer_months` above 0). The editor only checks `freezer-friendly`. |
| `equipment` | `["grill pan", "mixing bowl"]` | |
| `ingredients`, `steps` | | Plain text, one item each. Ingredients are cleaned up for searching. |
| `storage`, `reheat`, `tips` | | How to keep it, how to warm it up, and extra advice |

## Photo credits

The dish photos in `meal_prep_finder/static/recipes/` come from [TheMealDB](https://www.themealdb.com). Many show a similar dish, not exactly this recipe. Check TheMealDB's terms before you use them outside a personal or learning project.

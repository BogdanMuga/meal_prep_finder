"""Start Meal Prep Finder and open it in the browser.

This is the entry point of the packaged Windows app (MealPrepFinder.exe, built with
PyInstaller, see build.bat). It also works from source: `python run_app.py`.

  MealPrepFinder.exe            search and browse
  MealPrepFinder.exe --admin    also turn on the /admin recipe editor
  MealPrepFinder.exe --port 8080

The packaged app is bin/MealPrepFinder.exe plus bin/_internal/ (libraries, pages,
photos and the database, _internal/data/recipes.db). From source the database is
data/recipes.db next to this file.
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser
from pathlib import Path

HOST = "127.0.0.1"  # localhost only: the editor has no login


def data_dir() -> Path:
    """Where the database lives: bin/_internal/data in the packaged app (next to
    the bundled libraries, out of the way), or ./data when run from source."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "data"
    return Path(__file__).resolve().parent / "data"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run Meal Prep Finder on this PC.")
    parser.add_argument("--admin", action="store_true", help="turn on the /admin recipe editor")
    parser.add_argument("--port", type=int, default=5000, help="port to listen on (default 5000)")
    parser.add_argument("--no-browser", action="store_true", help="don't open the browser")
    args = parser.parse_args(argv)

    if args.admin:
        os.environ["ADMIN_ENABLED"] = "1"

    config = {}
    db_path = None
    if not os.environ.get("MEAL_PREP_DATABASE_URL"):
        db_path = data_dir() / "recipes.db"
        config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + str(db_path)

    from waitress import serve

    from meal_prep_finder.app import create_app

    app = create_app(config=config)
    url = f"http://{HOST}:{args.port}/"

    print("=" * 60)
    print(" Meal Prep Finder")
    print(f" Open:      {url}")
    print(f" Database:  {db_path or os.environ['MEAL_PREP_DATABASE_URL']}")
    print(f" Editor:    {'ON  (' + url + 'admin/)' if args.admin else 'off (start with --admin)'}")
    print(" Close this window (or press Ctrl+C) to stop.")
    print("=" * 60, flush=True)

    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    serve(app, host=HOST, port=args.port, threads=8)


if __name__ == "__main__":
    main()

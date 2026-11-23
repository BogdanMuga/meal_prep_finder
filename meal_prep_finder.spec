# PyInstaller spec for MealPrepFinder.exe (one-folder build). Build with build.bat.
# One-folder, not one-file: a one-file exe unpacks to a temp folder on every run,
# so uploaded photos would be lost.
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

pkg = Path("meal_prep_finder")


def tree(src: Path, patterns=("**/*",)):
    """(file, dest dir) pairs for every file under src, skipping caches."""
    out = []
    for pattern in patterns:
        for f in src.glob(pattern):
            if f.is_file() and "__pycache__" not in f.parts:
                out.append((str(f), str(f.parent)))
    return out


datas = (
    tree(pkg / "templates")
    + tree(pkg / "static")
    + tree(pkg / "data")
    # Alembic loads env.py and the revision files by path, so ship them as files.
    + tree(pkg / "migrations")
)

hiddenimports = (
    collect_submodules("alembic")
    + collect_submodules("meal_prep_finder")
    + ["logging.config", "sqlalchemy.dialects.sqlite"]
)

a = Analysis(
    ["run_app.py"],
    pathex=["."],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MealPrepFinder",
    console=True,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="MealPrepFinder", upx=False)

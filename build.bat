@echo off
rem Build bin\MealPrepFinder.exe, which runs on Windows PCs without Python.
rem bin\ holds only the exe and an _internal\ folder (libraries, pages, photos, database).
rem Rebuilding keeps the database and uploaded photos already in bin\.
setlocal
cd /d "%~dp0"
set "TMPBUILD=%TEMP%\MealPrepFinder-build"
if exist "%TMPBUILD%" rmdir /s /q "%TMPBUILD%"

".venv\Scripts\python.exe" -m pip install -q -e ".[package]" || goto :error
".venv\Scripts\python.exe" -m PyInstaller meal_prep_finder.spec --noconfirm --clean ^
    --distpath "%TMPBUILD%\dist" --workpath "%TMPBUILD%\work" || goto :error

rem Copy over the previous build without deleting anything, so _internal\data\ (the
rem database) and photos uploaded in the editor survive.
robocopy "%TMPBUILD%\dist\MealPrepFinder" "bin" /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto :error
rmdir /s /q "%TMPBUILD%"

echo.
echo Done: bin\MealPrepFinder.exe
echo Copy the whole bin folder to the other PC (MealPrepFinder.exe needs the _internal folder next to it).
exit /b 0

:error
echo Build failed.
exit /b 1

@echo off
setlocal
REM Builds dist\SpotifyQuickPlaylistManager.exe from this folder.
REM Just double-click this file. Needs Python 3.9+ installed (python.org).

cd /d "%~dp0"

REM Find Python: prefer the "py" launcher, fall back to "python".
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% --version >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install it from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" during setup, then run this again.
    goto :fail
)

REM Keep the build environment and temp files OUT of OneDrive so it doesn't
REM try to sync thousands of files.
set "VENV=%LOCALAPPDATA%\SpotifyQuickPlaylistManager-build\venv"
set "WORK=%LOCALAPPDATA%\SpotifyQuickPlaylistManager-build\work"

if not exist "%VENV%\Scripts\python.exe" (
    echo Creating build environment...
    %PY% -m venv "%VENV%"
    if errorlevel 1 goto :fail
)

echo Installing dependencies...
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip >nul
"%VENV%\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :fail

echo Building exe...
"%VENV%\Scripts\python.exe" -m PyInstaller --noconfirm --clean ^
    --onefile --windowed ^
    --name SpotifyQuickPlaylistManager ^
    --hidden-import pystray._win32 ^
    --collect-submodules keyring ^
    --workpath "%WORK%" --specpath "%WORK%" ^
    --distpath "%~dp0dist" ^
    main.py
if errorlevel 1 goto :fail

echo.
echo Done! Your app is at:
echo   %~dp0dist\SpotifyQuickPlaylistManager.exe
explorer "%~dp0dist"
pause
exit /b 0

:fail
echo.
echo Build failed - see the messages above.
pause
exit /b 1

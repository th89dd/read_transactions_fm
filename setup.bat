@echo off
REM Setze den Namen des virtuellen Environments
set VENV_NAME=venv

REM Überprüfen, ob Python installiert ist
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python ist nicht installiert. Bitte installiere Python und versuche es erneut.
    exit /b 1
)

REM Virtuelle Umgebung erstellen
echo Erstelle virtuelle Umgebung...
python -m venv %VENV_NAME%

REM Aktivieren der virtuellen Umgebung
echo Aktiviere virtuelle Umgebung...
call %VENV_NAME%\Scripts\activate

REM Installiere Abhängigkeiten aus requirements.txt
if exist requirements.txt (
    echo Installiere Abhängigkeiten...
    pip install --upgrade pip
    pip install -r requirements.txt
) else (
    echo requirements.txt wurde nicht gefunden.
)

echo Fertig!
exit /b 0
@echo off
REM Publica los .md convertidos en tu boveda de Obsidian.
REM Configura las carpetas en config.yaml:  output_dir (origen) y vault_dir (boveda).
cd /d "%~dp0"
python publicar.py
if errorlevel 1 (
    echo.
    echo Ocurrio un problema. Revisa el mensaje de arriba.
    pause
)

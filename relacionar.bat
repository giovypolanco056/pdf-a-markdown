@echo off
REM Detecta relaciones semanticas entre las notas de tu boveda de Obsidian.
REM Configura la boveda en config.yaml (vault_dir) y el umbral (relate_threshold).
REM El conocimiento del dominio se edita en  src\pdf2md\semantics\data\conceptos.yaml
cd /d "%~dp0"
python relacionar.py
if errorlevel 1 (
    echo.
    echo Ocurrio un problema. Revisa el mensaje de arriba.
    pause
)

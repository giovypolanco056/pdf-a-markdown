@echo off
REM Inicia el modo vigilancia: convierte a Markdown cada PDF que llegue
REM a documentos\entrada y mueve el original a documentos\procesados.
REM Cierra esta ventana (o pulsa Ctrl+C) para detenerlo.
cd /d "%~dp0"
python watch.py
if errorlevel 1 (
    echo.
    echo Ocurrio un error. Revisa el mensaje de arriba.
    pause
)

@echo off
REM Lanza la interfaz gráfica del conversor PDF -> Markdown.
REM Doble clic en este archivo para abrir la ventana.
cd /d "%~dp0"
python gui.py
if errorlevel 1 (
    echo.
    echo Ocurrio un error al iniciar la interfaz. Revisa el mensaje de arriba.
    pause
)

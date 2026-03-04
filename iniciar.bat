@echo off
title SISTEMA DE ASISTENCIA - MENU
color 0A

:menu
cls
echo ==========================================
echo      SISTEMA DE ASISTENCIA ESCOLAR
echo ==========================================
echo.
echo 1 - Instalar dependencias
echo 2 - Ejecutar sistema
echo 3 - Ver IP para red local
echo 4 - Salir
echo.
set /p opcion=Selecciona una opcion: 

if "%opcion%"=="1" goto instalar
if "%opcion%"=="2" goto ejecutar
if "%opcion%"=="3" goto ip
if "%opcion%"=="4" goto salir
goto menu

:instalar
cls
echo Instalando dependencias...
python -m pip install --upgrade pip
pip install -r requirements.txt
echo.
echo Dependencias instaladas correctamente.
pause
goto menu

:ejecutar
cls
echo Iniciando servidor...
echo.
echo Accede desde esta PC:
echo http://127.0.0.1:5000
echo.
echo Accede desde la red local usando la IP que aparece abajo.
echo.
ipconfig | findstr IPv4
echo.
python app.py
pause
goto menu

:ip
cls
echo Tu direccion IP en la red local es:
echo.
ipconfig | findstr IPv4
echo.
echo Los demas equipos deben entrar asi:
echo http://TU_IP:5000
echo.
pause
goto menu

:salir
exit
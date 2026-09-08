@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Baixai Forge - Atualizar yt-dlp

if not exist ".venv\Scripts\python.exe" (
  echo [ERRO] Execute INSTALAR.bat primeiro.
  pause
  exit /b 1
)

echo Versao atual:
".venv\Scripts\python.exe" -m yt_dlp --version

echo.
echo Atualizando yt-dlp e dependencias recomendadas...
".venv\Scripts\python.exe" -m pip install --upgrade "yt-dlp[default]"
if errorlevel 1 goto :erro

echo.
echo Nova versao:
".venv\Scripts\python.exe" -m yt_dlp --version

echo.
echo Atualizacao concluida.
pause
exit /b 0

:erro
echo.
echo [ERRO] Nao foi possivel atualizar o yt-dlp.
pause
exit /b 1

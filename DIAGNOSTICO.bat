@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Baixai Forge - Diagnostico

echo ========================================================================
echo                       BAIXAI FORGE - DIAGNOSTICO
echo ========================================================================

echo [Python]
where python 2>nul
python --version 2>nul

echo.
echo [Ambiente virtual]
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" --version
  ".venv\Scripts\python.exe" -c "import fastapi, uvicorn, yt_dlp; print('FastAPI:', fastapi.__version__); print('Uvicorn:', uvicorn.__version__); print('yt-dlp:', yt_dlp.version.__version__)"
) else (
  echo NAO ENCONTRADO - execute INSTALAR.bat
)

echo.
echo [FFmpeg]
where ffmpeg 2>nul
ffmpeg -version 2>nul | findstr /B "ffmpeg version"

echo.
echo [JavaScript runtime - recomendado pelo yt-dlp para suporte completo]
where deno 2>nul
where node 2>nul
where bun 2>nul

echo.
echo [Pastas]
if exist "data" (echo data: OK) else (echo data: sera criada na primeira execucao)
if exist "data\logs\baixai-forge.log" (echo log: data\logs\baixai-forge.log) else (echo log: ainda nao criado)

echo.
echo Diagnostico concluido.
pause

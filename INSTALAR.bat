@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
title Baixai Forge v1.1.0 - Instalacao

echo ========================================================================
echo                    BAIXAI FORGE v1.1.0 - INSTALADOR
echo ========================================================================
echo.

where py >nul 2>&1
if %errorlevel%==0 (
  set "PY=py -3"
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo [ERRO] Python nao encontrado.
    echo Instale Python 3.11 ou superior e marque "Add Python to PATH".
    goto :erro
  )
  set "PY=python"
)

%PY% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if errorlevel 1 (
  echo [ERRO] Python 3.11 ou superior e necessario.
  %PY% --version
  goto :erro
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/5] Criando ambiente virtual...
  %PY% -m venv .venv
  if errorlevel 1 goto :erro
) else (
  echo [1/5] Ambiente virtual existente: OK
)

echo [2/5] Atualizando ferramentas de instalacao...
".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :erro

echo [3/5] Instalando dependencias...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :erro

if not exist ".env" (
  echo Criando .env a partir de .env.example...
  copy /Y ".env.example" ".env" >nul
)

echo [4/5] Validando importacoes...
".venv\Scripts\python.exe" -c "import fastapi, uvicorn, yt_dlp, jinja2, dotenv, httpx; import baixai_forge; print('Python/Dependencias: OK | Baixai Forge', baixai_forge.__version__)"
if errorlevel 1 goto :erro

echo [5/5] Verificando FFmpeg...
where ffmpeg >nul 2>&1
if errorlevel 1 (
  echo [AVISO] FFmpeg nao foi encontrado no PATH.
  echo         O sistema abre normalmente, mas MP3 e alguns videos podem falhar.
  echo         Consulte docs\TROUBLESHOOTING.md.
) else (
  echo FFmpeg: OK
)

echo.
echo ========================================================================
echo Instalacao concluida com sucesso.
echo Execute INICIAR_BAIXAI_FORGE.bat
echo ========================================================================
pause
exit /b 0

:erro
echo.
echo [ERRO] A instalacao falhou. Leia as mensagens acima.
echo Consulte docs\TROUBLESHOOTING.md se precisar.
pause
exit /b 1

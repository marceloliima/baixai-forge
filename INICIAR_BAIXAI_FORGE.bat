@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Baixai Forge v1.1.0

if not exist ".venv\Scripts\python.exe" (
  echo Primeira execucao detectada. Abrindo instalador...
  call INSTALAR.bat
  if errorlevel 1 exit /b 1
)

echo ========================================================================
echo                         BAIXAI FORGE v1.1.0
echo ========================================================================
echo Interface local: http://127.0.0.1:8765
echo Para encerrar com seguranca, pressione CTRL+C.
echo.

".venv\Scripts\python.exe" -m baixai_forge
set "EXITCODE=%errorlevel%"

echo.
if not "%EXITCODE%"=="0" (
  echo [ERRO] O Baixai Forge encerrou com codigo %EXITCODE%.
  echo Consulte data\logs\baixai-forge.log e execute DIAGNOSTICO.bat.
)
pause
exit /b %EXITCODE%

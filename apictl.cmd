@echo off
chcp 65001 >nul 2>nul
setlocal enabledelayedexpansion
set "APICTL_PY=%~dp0apictl.py"
set "PY="
where python >nul 2>nul
if not errorlevel 1 set "PY=python"
if not defined PY (
  where py >nul 2>nul
  if not errorlevel 1 set "PY=py -3"
)
if not defined PY (
  if exist "B:\school\huanjin\conda\python.exe" set "PY=B:\school\huanjin\conda\python.exe"
)
if not defined PY (
  echo Python 3.8+ not found. Install it or add python to PATH.
  exit /b 9009
)
%PY% "%APICTL_PY%" %*
set "RC=!errorlevel!"
if "%~1"=="" pause
exit /b %RC%

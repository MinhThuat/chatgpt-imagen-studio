@echo off
REM Mo Imagegen Studio tren Windows: terminal (Claude) o duoi + gallery o tren.
REM Yeu cau: Git for Windows (git + Git Bash), Python 3, Node.js. Xem setup.bat.
cd /d "%~dp0"
call "%~dp0_env.bat"

set "PORT=%~1"
if "%PORT%"=="" set "PORT=8760"

REM Model codex mac dinh (gpt-5.5 da bi go). Doi o day -> terminal + moi script gen con deu thua huong.
if "%CHATGPT_IMAGEGEN_MODEL%"=="" set "CHATGPT_IMAGEGEN_MODEL=gpt-5.6-sol"

REM Tu cap nhat code moi tu git moi 60s (chay autoupdate.sh qua Git Bash o nen).
where bash >nul 2>&1 && start "" /b bash autoupdate.sh

REM Mo trinh duyet sau 2s (cho server len). PowerShell luon co san tren Windows.
start "" /b powershell -NoProfile -Command "Start-Sleep 2; Start-Process 'http://127.0.0.1:%PORT%'"

python imagegen_studio.py --port %PORT%

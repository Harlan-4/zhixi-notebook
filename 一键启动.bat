@echo off
chcp 65001 >nul
title 智析错题本 - 一键启动
cd /d "%~dp0"

echo ==============================================
echo   智析错题本 一键启动
echo ==============================================

if not exist "backend\.venv\Scripts\python.exe" (
  echo [错误] 未找到后端虚拟环境 backend\.venv
  echo 请先在 backend 目录执行:
  echo   python -m venv .venv
  echo   .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)

where npx >nul 2>&1
if errorlevel 1 (
  echo [错误] 未找到 node/npx 命令，请先安装 Node.js ^(https://nodejs.org^)
  pause
  exit /b 1
)

echo [1/4] 启动后端 FastAPI（端口8000，新窗口）...
start "智析错题本-后端-勿关" cmd /k "cd /d %~dp0backend && .venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo [2/4] 启动前端 Vite（端口5173，新窗口）...
start "智析错题本-前端-勿关" cmd /k "cd /d %~dp0frontend && npx vite --port 5173"

echo [3/4] 等待服务就绪（最多约30秒）...
powershell -NoProfile -Command "$ok=$false; for($i=0;$i -lt 15;$i++){ Start-Sleep -Seconds 2; try{ Invoke-WebRequest -UseBasicParsing http://localhost:5173 -TimeoutSec 2 | Out-Null; $ok=$true; break }catch{} }; if($ok){exit 0}else{exit 1}"
if errorlevel 1 (
  echo [提示] 前端暂未就绪（首次运行 npx 可能较慢），仍将打开浏览器。
)

echo [4/4] 打开浏览器 http://localhost:5173
start "" "http://localhost:5173"

echo.
echo 已完成！若浏览器未自动打开，请手动访问: http://localhost:5173
echo 停止方法: 关闭"智析错题本-后端"和"智析错题本-前端"两个窗口。
echo 本窗口可以关闭。
pause >nul

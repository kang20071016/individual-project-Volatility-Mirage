@echo off
chcp 65001 > nul
cd /d "%~dp0"
set "VM_PYTHON=python"
if exist "D:\Users\LENOVO\Desktop\数据分析与可视化\.venv\Scripts\python.exe" set "VM_PYTHON=D:\Users\LENOVO\Desktop\数据分析与可视化\.venv\Scripts\python.exe"
if exist ".venv\Scripts\python.exe" set "VM_PYTHON=.venv\Scripts\python.exe"
echo Starting Volatility Mirage at http://localhost:8503/
echo Keep this window open while using the preview.
"%VM_PYTHON%" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8503 --browser.gatherUsageStats false
pause

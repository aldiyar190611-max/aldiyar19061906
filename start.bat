@echo off
echo Starting LiquidityAI Dashboard...
cd /d %~dp0
.venv\Scripts\python.exe -W ignore -m streamlit run dashboard/app.py --server.port 8501 --theme.base dark
pause

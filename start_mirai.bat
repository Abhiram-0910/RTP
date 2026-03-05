@echo off
setlocal
set "PYTHONIOENCODING=utf-8"

REM Change to the directory where this script lives
cd /d "%~dp0"

echo ============================================================
echo  MIRAI AI - Movie ^& TV Recommendation Engine
echo ============================================================

REM Check if venv exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found at .\venv\
    echo Please create it: python -m venv venv
    echo Then install: .\venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM Activate venv
call "venv\Scripts\activate.bat"

REM Check if FAISS index exists; if not, run ingest first
if not exist "data\faiss_index\index.faiss" (
    echo [INFO] FAISS index not found. Running data ingest ^(first-time setup^)...
    echo [INFO] This may take 30-60 minutes. Please do not close this window.
    cd backend
    python ingest_all_data.py
    cd ..
    echo [INFO] Ingest complete.
)

REM Start backend in a new window
echo [1/2] Starting MIRAI backend on http://localhost:8000 ...
start "MIRAI Backend" cmd /k "cd /d "%~dp0backend" && uvicorn enhanced_main:app --host 0.0.0.0 --port 8000 --reload"

REM Wait for backend to initialize
echo [INFO] Waiting for backend to start...
timeout /t 6 /nobreak >nul

REM Start frontend
echo [2/2] Starting MIRAI frontend on http://localhost:8501 ...
cd frontend
streamlit run enhanced_app.py --server.port 8501 --server.headless false

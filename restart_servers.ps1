# Stop any running python processes
Stop-Process -Name "python" -Force -ErrorAction SilentlyContinue

# Wait a moment
Start-Sleep -Seconds 2

# Start Backend in a new window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; uvicorn enhanced_main:app --port 8000 --reload"

# Wait for backend to start
Start-Sleep -Seconds 5

# Start Frontend in a new window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; streamlit run enhanced_app.py --server.port 8501"

Write-Host "Servers restarted! Please check the new windows."

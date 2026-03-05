#!/bin/bash

echo "Starting MIRAI AI..."

# Start backend
echo "Starting backend server..."
cd backend
uvicorn enhanced_main:app --port 8000 --reload &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 5

# Start frontend
echo "Starting frontend..."
cd frontend
streamlit run enhanced_app.py

# Kill backend on exit
trap "kill $BACKEND_PID" EXIT

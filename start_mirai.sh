#!/bin/bash

echo "Starting Movie and TV Shows Recommending Engine AI..."

# Start backend
echo "Starting backend server..."
cd backend
uvicorn enhanced_main:app --host 0.0.0.0 --port 8000 --workers 4 --loop uvloop --http httptools &
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

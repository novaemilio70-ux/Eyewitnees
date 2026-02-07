#!/bin/bash

# Start script for EyeWitness Web Application
# Usage: ./start.sh [project_name]
# Example: ./start.sh laboon

echo "Starting EyeWitness Web Application..."

# Check if project name is provided
if [ -n "$1" ]; then
    export EYEWITNESS_PROJECT="$1"
    echo "Using project: $EYEWITNESS_PROJECT"
fi

# Check if virtual environments exist
if [ ! -d "backend/venv" ]; then
    echo "Creating backend virtual environment..."
    cd backend
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cd ..
fi

if [ ! -d "frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
fi

# Start backend in background
echo "Starting backend server..."
cd backend
source venv/bin/activate
python main.py &
BACKEND_PID=$!
cd ..

# Wait a bit for backend to start
sleep 3

# Start frontend
echo "Starting frontend server..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "=========================================="
echo "EyeWitness Web Application is running!"
echo "=========================================="
echo "Backend:  http://localhost:5000"
echo "Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Wait for user interrupt
trap "kill $BACKEND_PID $FRONTEND_PID" EXIT
wait


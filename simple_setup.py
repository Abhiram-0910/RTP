#!/usr/bin/env python3
"""
MIRAI AI Simple Setup Script
Quick setup for the revolutionary movie recommendation system
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd, description=""):
    """Run a command and handle errors"""
    try:
        if description:
            print(f"🔄 {description}")
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            if description:
                print(f"✅ {description} - Success")
            return True
        else:
            print(f"❌ {description} - Failed")
            print(f"Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {description} - Error: {str(e)}")
        return False

def main():
    """Main setup function"""
    print("🤖 MIRAI AI Simple Setup")
    print("=" * 50)
    
    project_root = Path(__file__).parent
    
    # Step 1: Create data directories
    print("📁 Creating data directories...")
    data_dirs = ["data", "data/faiss_index", "data/cache", "data/logs"]
    for dir_name in data_dirs:
        dir_path = project_root / dir_name
        dir_path.mkdir(exist_ok=True)
        print(f"✅ Created {dir_name}")
    
    # Step 2: Create .env file if it doesn't exist
    env_file = project_root / ".env"
    if not env_file.exists():
        print("⚙️  Creating .env file...")
        env_content = f"""# MIRAI AI Configuration
# Add your API keys here:
GEMINI_API_KEY=your_gemini_api_key_here
TMDB_API_KEY=your_tmdb_api_key_here
DATABASE_URL=sqlite:///./mirai.db
DEBUG=true
"""
        with open(env_file, 'w') as f:
            f.write(env_content)
        print("✅ .env file created")
        print("📝 Please add your API keys to the .env file")
    else:
        print("✅ .env file already exists")
    
    # Step 3: Install basic requirements
    print("📚 Installing basic requirements...")
    basic_requirements = [
        "fastapi==0.110.0",
        "uvicorn==0.27.1",
        "streamlit==1.28.2",
        "pandas==2.1.4",
        "numpy==1.26.4",
        "requests==2.31.0",
        "python-dotenv==1.0.1",
        "sqlalchemy==2.0.25",
        "langchain==0.1.16",
        "sentence-transformers==2.2.2",
        "faiss-cpu==1.13.2",
        "googletrans==4.0.0",
        "scikit-learn==1.3.2"
    ]
    
    for req in basic_requirements:
        if not run_command(f"pip install {req}", f"Installing {req.split('==')[0]}"):
            print(f"⚠️  Warning: Failed to install {req}, continuing...")
    
    # Step 4: Initialize database
    print("🗄️  Initializing database...")
    if not run_command(f"python -c \"from backend.enhanced_database import init_enhanced_db; init_enhanced_db()\"", "Database initialization"):
        print("⚠️  Warning: Database initialization failed, but continuing...")
    
    # Step 5: Create startup scripts
    print("🚀 Creating startup scripts...")
    
    # Windows batch file
    with open("start_mirai.bat", "w") as f:
        f.write("""@echo off
echo Starting MIRAI AI...

REM Start backend
echo Starting backend server...
start cmd /k "cd backend && uvicorn enhanced_main:app --port 8000 --reload"
timeout /t 5 /nobreak > nul

REM Start frontend
echo Starting frontend...
cd frontend
streamlit run enhanced_app.py
""")
    
    # Unix shell script
    with open("start_mirai.sh", "w") as f:
        f.write("""#!/bin/bash

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
""")
    
    if os.name != 'nt':
        os.chmod("start_mirai.sh", 0o755)
    
    print("✅ Startup scripts created")
    
    # Step 6: Final instructions
    print("\n" + "=" * 50)
    print("🎉 MIRAI AI Setup Complete!")
    print("=" * 50)
    print()
    print("📋 Next Steps:")
    print("1. Add your API keys to the .env file:")
    print("   - GEMINI_API_KEY: Get from Google AI Studio")
    print("   - TMDB_API_KEY: Get from The Movie Database")
    print()
    print("🚀 To start MIRAI AI:")
    if os.name == 'nt':
        print("   Run: start_mirai.bat")
    else:
        print("   Run: ./start_mirai.sh")
    print()
    print("🌐 Access points:")
    print("   - Frontend: http://localhost:8501")
    print("   - Backend API: http://localhost:8000")
    print("   - API Docs: http://localhost:8000/docs")
    print()
    print("📚 For data collection (optional):")
    print("   python backend/tmdb_data_collector.py")
    print()
    print("🎯 Features ready to use:")
    print("   - AI-powered movie recommendations")
    print("   - Multilingual search support")
    print("   - Real-time streaming platform data")
    print("   - Advanced filtering and sorting")
    print("   - User feedback and ratings")
    print("   - Personalized AI explanations")
    print()
    print("❓ Need help? Check the README.md file")
    print()
    print("🌟 Enjoy MIRAI AI - Your revolutionary movie discovery engine!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        sys.exit(1)
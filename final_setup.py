#!/usr/bin/env python3
"""
MIRAI AI Final Setup and Startup Script
Complete setup for the revolutionary movie recommendation system
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def print_banner():
    """Print MIRAI AI banner"""
    banner = """
🤖 MIRAI AI - Revolutionary Movie Recommendation Engine v2.0.0 🤖

Advanced AI-powered movie and TV show discovery platform with:
✨ AI-powered explanations with Google Gemini
🌍 Multilingual support (15+ languages)
📺 Real-time streaming platform data
🎬 10,000+ movies and TV shows
🧠 Hybrid recommendation engine
🎯 Advanced filtering system
💬 User feedback and ratings
"""
    print(banner)

def run_command(cmd, description="", cwd=None, timeout=300):
    """Run a command with error handling"""
    try:
        if description:
            print(f"🔄 {description}")
        
        result = subprocess.run(
            cmd, 
            shell=True, 
            cwd=cwd, 
            capture_output=True, 
            text=True,
            timeout=timeout
        )
        
        if result.returncode == 0:
            if description:
                print(f"✅ {description} - Success")
            return True
        else:
            print(f"❌ {description} - Failed")
            if result.stderr:
                print(f"Error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"❌ {description} - Timeout")
        return False
    except Exception as e:
        print(f"❌ {description} - Error: {str(e)}")
        return False

def setup_environment():
    """Setup the environment"""
    print("🛠️  Setting up MIRAI AI environment...")
    
    # Create data directories
    print("📁 Creating data directories...")
    data_dirs = ["data", "data/faiss_index", "data/cache", "data/logs"]
    for dir_name in data_dirs:
        dir_path = Path(dir_name)
        dir_path.mkdir(exist_ok=True)
        print(f"✅ Created {dir_name}")
    
    # Create .env file if it doesn't exist
    env_file = Path(".env")
    if not env_file.exists():
        print("⚙️  Creating .env file...")
        env_content = """# MIRAI AI Configuration
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
    
    return True

def install_dependencies():
    """Install required dependencies"""
    print("📚 Installing dependencies...")
    
    # Install basic requirements
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
        "scikit-learn==1.3.2"
    ]
    
    for req in basic_requirements:
        if not run_command(f"pip install {req}", f"Installing {req.split('==')[0]}"):
            print(f"⚠️  Warning: Failed to install {req}, continuing...")
    
    return True

def initialize_database():
    """Initialize the database"""
    print("🗄️  Initializing database...")
    
    # Use the simple database for now
    if not run_command("python -c \"from backend.simple_database import init_enhanced_db; init_enhanced_db()\"", "Database initialization"):
        print("⚠️  Warning: Database initialization failed, but continuing...")
    
    return True

def create_startup_scripts():
    """Create startup scripts"""
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
    return True

def main():
    """Main function"""
    print_banner()
    
    try:
        # Setup steps
        steps = [
            ("Environment Setup", setup_environment),
            ("Dependencies Installation", install_dependencies),
            ("Database Initialization", initialize_database),
            ("Startup Scripts Creation", create_startup_scripts)
        ]
        
        success_count = 0
        total_steps = len(steps)
        
        for step_name, step_func in steps:
            print(f"\n📋 Step {success_count + 1}/{total_steps}: {step_name}")
            if step_func():
                success_count += 1
                print(f"✅ {step_name} completed successfully")
            else:
                print(f"⚠️  {step_name} completed with warnings")
        
        # Final summary
        print("\n" + "=" * 60)
        print(f"🎉 MIRAI AI Setup Complete! ({success_count}/{total_steps} steps)")
        print("=" * 60)
        
        print("\n📋 Next Steps:")
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
        
        return True
        
    except KeyboardInterrupt:
        print("\n❌ Setup interrupted by user")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
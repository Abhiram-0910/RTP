#!/usr/bin/env python3
"""
MIRAI AI Enhanced Setup Script
Comprehensive setup for the revolutionary movie recommendation system
"""

import os
import sys
import subprocess
import json
import time
from pathlib import Path
from typing import List, Dict, Optional
import platform

class Colors:
    """Color codes for terminal output"""
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'

class MIRAISetup:
    """Main setup class for MIRAI AI"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.backend_dir = self.project_root / "backend"
        self.frontend_dir = self.project_root / "frontend"
        self.data_dir = self.project_root / "data"
        self.venv_path = self.project_root / "venv"
        self.os_type = platform.system()
        self.python_executable = sys.executable
        
        # Setup configuration
        self.config = {
            "project_name": "MIRAI AI",
            "version": "2.0.0",
            "description": "Revolutionary AI-Powered Movie & TV Recommendation Engine",
            "features": [
                "AI-powered explanations with Gemini",
                "Multilingual support (15+ languages)",
                "Real-time streaming platform data",
                "10,000+ movies and TV shows",
                "Hybrid recommendation engine",
                "Advanced filtering system",
                "User feedback loop",
                "PostgreSQL database",
                "Sentiment analysis",
                "Recommendation diversity algorithms"
            ]
        }
    
    def print_banner(self):
        """Print MIRAI AI banner"""
        banner = f"""
{Colors.CYAN}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║    🤖 MIRAI AI - Revolutionary Movie Recommendation Engine v2.0.0 🤖         ║
║                                                                              ║
║    {Colors.WHITE}Advanced AI-powered movie and TV show discovery platform{Colors.CYAN}              ║
║    {Colors.WHITE}with multilingual support, real-time data, and personalized{Colors.CYAN}         ║
║    {Colors.WHITE}explanations powered by Google's Gemini AI.{Colors.CYAN}                        ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
{Colors.RESET}
        """
        print(banner)
    
    def print_step(self, step: str, description: str):
        """Print setup step with formatting"""
        print(f"{Colors.BLUE}{Colors.BOLD}[STEP] {step}{Colors.RESET}")
        print(f"{Colors.WHITE}{description}{Colors.RESET}")
        print()
    
    def print_success(self, message: str):
        """Print success message"""
        print(f"{Colors.GREEN}✅ {message}{Colors.RESET}")
    
    def print_warning(self, message: str):
        """Print warning message"""
        print(f"{Colors.YELLOW}⚠️  {message}{Colors.RESET}")
    
    def print_error(self, message: str):
        """Print error message"""
        print(f"{Colors.RED}❌ {message}{Colors.RESET}")
    
    def print_info(self, message: str):
        """Print info message"""
        print(f"{Colors.CYAN}ℹ️  {message}{Colors.RESET}")
    
    def run_command(self, command: List[str], cwd: Optional[Path] = None, 
                   description: str = "", shell: bool = False) -> bool:
        """Run shell command with error handling"""
        try:
            if description:
                self.print_info(f"Running: {' '.join(command)}")
            
            result = subprocess.run(
                command,
                cwd=cwd or self.project_root,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                if description:
                    self.print_success(description)
                return True
            else:
                self.print_error(f"Command failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.print_error("Command timed out")
            return False
        except Exception as e:
            self.print_error(f"Command error: {str(e)}")
            return False
    
    def check_python_version(self) -> bool:
        """Check Python version compatibility"""
        self.print_step("Checking Python Version", "Verifying Python 3.8+ is available")
        
        version = sys.version_info
        if version.major == 3 and version.minor >= 8:
            self.print_success(f"Python {version.major}.{version.minor}.{version.micro} is compatible")
            return True
        else:
            self.print_error(f"Python 3.8+ required, found {version.major}.{version.minor}.{version.micro}")
            return False
    
    def create_directories(self) -> bool:
        """Create necessary project directories"""
        self.print_step("Creating Project Structure", "Setting up directory structure")
        
        directories = [
            self.data_dir,
            self.data_dir / "faiss_index",
            self.data_dir / "cache",
            self.data_dir / "logs",
            self.backend_dir / "models",
            self.backend_dir / "utils",
            self.frontend_dir / "assets",
            self.frontend_dir / "components"
        ]
        
        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                self.print_info(f"Created: {directory}")
            except Exception as e:
                self.print_error(f"Failed to create {directory}: {str(e)}")
                return False
        
        self.print_success("Project directories created successfully")
        return True
    
    def create_virtual_environment(self) -> bool:
        """Create Python virtual environment"""
        self.print_step("Creating Virtual Environment", "Setting up isolated Python environment")
        
        if self.venv_path.exists():
            self.print_warning("Virtual environment already exists, skipping creation")
            return True
        
        # Create virtual environment
        success = self.run_command(
            [self.python_executable, "-m", "venv", str(self.venv_path)],
            description="Virtual environment created"
        )
        
        if success:
            # Get virtual environment Python executable
            if self.os_type == "Windows":
                self.venv_python = self.venv_path / "Scripts" / "python.exe"
                self.venv_pip = self.venv_path / "Scripts" / "pip.exe"
            else:
                self.venv_python = self.venv_path / "bin" / "python"
                self.venv_pip = self.venv_path / "bin" / "pip"
            
            self.print_success(f"Virtual environment created at {self.venv_path}")
            return True
        
        return False
    
    def install_dependencies(self) -> bool:
        """Install Python dependencies"""
        self.print_step("Installing Dependencies", "Installing required Python packages")
        
        # Upgrade pip
        success = self.run_command(
            [str(self.venv_pip), "install", "--upgrade", "pip"],
            description="Pip upgraded"
        )
        
        if not success:
            return False
        
        # Install basic requirements first
        basic_requirements = [
            "fastapi==0.110.0",
            "uvicorn==0.27.1",
            "streamlit==1.28.2",
            "pandas==2.1.4",
            "numpy==1.26.4",
            "requests==2.31.0",
            "python-dotenv==1.0.1"
        ]
        
        for requirement in basic_requirements:
            success = self.run_command(
                [str(self.venv_pip), "install", requirement],
                description=f"Installed {requirement}"
            )
            if not success:
                self.print_warning(f"Failed to install {requirement}, continuing...")
        
        # Install enhanced requirements
        self.print_info("Installing enhanced requirements...")
        enhanced_req_path = self.project_root / "requirements_enhanced.txt"
        
        if enhanced_req_path.exists():
            success = self.run_command(
                [str(self.venv_pip), "install", "-r", str(enhanced_req_path)],
                description="Enhanced requirements installed"
            )
            
            if success:
                self.print_success("All dependencies installed successfully")
                return True
            else:
                self.print_warning("Some enhanced requirements failed, but basic setup is complete")
                return True
        else:
            self.print_warning("Enhanced requirements file not found, using basic requirements")
            return True
    
    def create_environment_file(self) -> bool:
        """Create environment configuration file"""
        self.print_step("Creating Environment Configuration", "Setting up .env file")
        
        env_content = f"""# MIRAI AI Environment Configuration
# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# API Keys (Add your keys here)
GEMINI_API_KEY=your_gemini_api_key_here
TMDB_API_KEY=your_tmdb_api_key_here
OPENAI_API_KEY=your_openai_api_key_here  # Optional

# Database Configuration
DATABASE_URL=sqlite:///./mirai.db
# For PostgreSQL: postgresql://user:password@localhost:5432/mirai

# Application Settings
DEBUG=true
ENVIRONMENT=development
LOG_LEVEL=INFO
MAX_RECOMMENDATIONS=10
CACHE_TTL=3600

# AI Settings
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
AI_EXPLANATION_STYLE=detailed
DIVERSITY_LEVEL=0.7
SENTIMENT_ANALYSIS=true

# Performance Settings
WORKERS=4
THREADS=8
TIMEOUT=30
RATE_LIMIT=100

# Features
ENABLE_MULTILINGUAL=true
ENABLE_STREAMING_DATA=true
ENABLE_USER_FEEDBACK=true
ENABLE_TRENDING=true
ENABLE_ANALYTICS=true

# Security
SECRET_KEY=your_secret_key_here_change_this
JWT_SECRET=your_jwt_secret_here_change_this
CORS_ORIGINS=*

# External Services
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER=redis://localhost:6379/1
CELERY_BACKEND=redis://localhost:6379/2
"""
        
        env_path = self.project_root / ".env"
        
        try:
            with open(env_path, 'w') as f:
                f.write(env_content)
            
            self.print_success(f"Environment file created at {env_path}")
            self.print_info("Please update the API keys in the .env file before running the application")
            return True
            
        except Exception as e:
            self.print_error(f"Failed to create .env file: {str(e)}")
            return False
    
    def create_setup_script(self) -> bool:
        """Create automated setup script"""
        self.print_step("Creating Setup Scripts", "Generating automated setup scripts")
        
        # Windows setup script
        if self.os_type == "Windows":
            setup_bat = self.project_root / "setup.bat"
            bat_content = f"""@echo off
echo {Colors.CYAN}Setting up MIRAI AI...{Colors.RESET}

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo Activating virtual environment...
call venv\\Scripts\\activate.bat

REM Install requirements
echo Installing requirements...
pip install --upgrade pip
pip install -r requirements_enhanced.txt

REM Create data directories
echo Creating data directories...
mkdir data\\faiss_index 2>nul
mkdir data\\cache 2>nul
mkdir data\\logs 2>nul

echo {Colors.GREEN}Setup complete!{Colors.RESET}
echo.
echo {Colors.YELLOW}Next steps:{Colors.RESET}
echo 1. Add your API keys to .env file
echo 2. Run data collection: python backend/tmdb_data_collector.py
echo 3. Start backend: uvicorn backend.enhanced_main:app --port 8000
echo 4. Start frontend: streamlit run frontend/enhanced_app.py
echo.
pause
"""
            
            try:
                with open(setup_bat, 'w') as f:
                    f.write(bat_content)
                self.print_success("Windows setup script created")
            except Exception as e:
                self.print_error(f"Failed to create Windows setup script: {str(e)}")
                return False
        
        # Unix setup script
        setup_sh = self.project_root / "setup.sh"
        sh_content = f"""#!/bin/bash

{Colors.CYAN}Setting up MIRAI AI...{Colors.RESET}

# Colors for output
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
NC='\\033[0m' # No Color

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo "Installing requirements..."
pip install --upgrade pip
pip install -r requirements_enhanced.txt

# Create data directories
echo "Creating data directories..."
mkdir -p data/faiss_index
mkdir -p data/cache
mkdir -p data/logs

echo "${{GREEN}}Setup complete!${{NC}}"
echo
echo "${{YELLOW}}Next steps:${{NC}}"
echo "1. Add your API keys to .env file"
echo "2. Run data collection: python backend/tmdb_data_collector.py"
echo "3. Start backend: uvicorn backend.enhanced_main:app --port 8000"
echo "4. Start frontend: streamlit run frontend/enhanced_app.py"
echo
"""
        
        try:
            with open(setup_sh, 'w') as f:
                f.write(sh_content)
            
            # Make executable
            os.chmod(setup_sh, 0o755)
            self.print_success("Unix setup script created")
            
        except Exception as e:
            self.print_error(f"Failed to create Unix setup script: {str(e)}")
            return False
        
        return True
    
    def create_run_scripts(self) -> bool:
        """Create run scripts for easy startup"""
        self.print_step("Creating Run Scripts", "Generating startup scripts")
        
        # Windows run script
        if self.os_type == "Windows":
            run_bat = self.project_root / "run.bat"
            bat_content = f"""@echo off
echo {Colors.CYAN}Starting MIRAI AI...{Colors.RESET}

REM Activate virtual environment
call venv\\Scripts\\activate.bat

REM Start backend in background
echo Starting backend server...
start cmd /k "cd backend && uvicorn enhanced_main:app --port 8000 --reload"
timeout /t 5 /nobreak > nul

REM Start frontend
echo Starting frontend...
cd frontend
streamlit run enhanced_app.py

pause
"""
            
            try:
                with open(run_bat, 'w') as f:
                    f.write(bat_content)
                self.print_success("Windows run script created")
            except Exception as e:
                self.print_error(f"Failed to create Windows run script: {str(e)}")
                return False
        
        # Unix run script
        run_sh = self.project_root / "run.sh"
        sh_content = f"""#!/bin/bash

{Colors.CYAN}Starting MIRAI AI...{Colors.RESET}

# Activate virtual environment
source venv/bin/activate

# Start backend in background
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
"""
        
        try:
            with open(run_sh, 'w') as f:
                f.write(sh_content)
            
            os.chmod(run_sh, 0o755)
            self.print_success("Unix run script created")
            
        except Exception as e:
            self.print_error(f"Failed to create Unix run script: {str(e)}")
            return False
        
        return True
    
    def create_documentation(self) -> bool:
        """Create enhanced documentation"""
        self.print_step("Creating Documentation", "Generating comprehensive documentation")
        
        readme_content = f"""# 🤖 MIRAI AI - Revolutionary Movie Recommendation Engine

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-green.svg)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28.2-red.svg)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🌟 Overview

MIRAI AI is a revolutionary, AI-powered movie and TV show recommendation engine that transforms how you discover content. With advanced machine learning, multilingual support, and personalized AI explanations, MIRAI AI delivers an unparalleled entertainment discovery experience.

## ✨ Key Features

### 🤖 AI-Powered Intelligence
- **Google Gemini Integration**: Personalized explanations powered by advanced AI
- **Multilingual Support**: Search and receive recommendations in 15+ languages
- **Sentiment Analysis**: Understand user preferences through advanced NLP
- **Diversity Algorithms**: Avoid echo chambers with intelligent content diversity

### 📊 Advanced Recommendation Engine
- **Hybrid Filtering**: Combines content-based and collaborative filtering
- **Real-time Learning**: Improves recommendations based on user interactions
- **Serendipitous Discovery**: Pleasant surprises beyond your usual preferences
- **Trending Integration**: Stay updated with popular and trending content

### 🎬 Comprehensive Content Database
- **10,000+ Titles**: Movies and TV shows from around the world
- **Real-time Streaming Data**: Live platform availability (Netflix, Prime, Disney+, etc.)
- **Rich Metadata**: Genres, cast, ratings, reviews, and more
- **Multi-language Content**: Support for global cinema and television

### 🚀 Technical Excellence
- **PostgreSQL Database**: Scalable, high-performance data storage
- **FAISS Vector Search**: Lightning-fast similarity search
- **Redis Caching**: Blazing-fast response times
- **Async Processing**: Non-blocking operations for better performance

## 🛠️ Technology Stack

### Backend
- **FastAPI**: Modern, fast web framework
- **SQLAlchemy**: SQL toolkit and ORM
- **PostgreSQL**: Advanced relational database
- **FAISS**: Facebook AI Similarity Search
- **Sentence Transformers**: Multilingual embeddings
- **Google Gemini**: AI explanations
- **Redis**: In-memory caching
- **Celery**: Distributed task queue

### Frontend
- **Streamlit**: Data app framework
- **React Components**: Interactive UI elements
- **Chart.js**: Data visualization
- **Tailwind CSS**: Utility-first CSS framework

### AI/ML
- **Transformers**: State-of-the-art NLP models
- **Scikit-learn**: Machine learning library
- **TensorFlow/PyTorch**: Deep learning frameworks
- **Hugging Face**: Model hub and transformers

## 📋 Prerequisites

- Python 3.8 or higher
- 8GB+ RAM recommended
- 10GB+ free disk space
- Internet connection for API calls

## 🚀 Quick Start

### 1. Clone and Setup
```bash
git clone <repository-url>
cd movie-rec-project
```

### 2. Run Automated Setup
```bash
# Windows
setup.bat

# Linux/Mac
chmod +x setup.sh
./setup.sh
```

### 3. Configure API Keys
Edit the `.env` file and add your API keys:
```
GEMINI_API_KEY=your_gemini_api_key_here
TMDB_API_KEY=your_tmdb_api_key_here
```

### 4. Start the Application
```bash
# Windows
run.bat

# Linux/Mac
chmod +x run.sh
./run.sh
```

### 5. Access MIRAI AI
- Frontend: http://localhost:8501
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## 📊 Data Collection

### TMDB Data Collection
```bash
cd backend
python tmdb_data_collector.py
```

This will collect:
- 10,000+ movies and TV shows
- Real-time streaming platform data
- Trending content
- Detailed metadata and reviews

### Database Migration
```bash
cd backend
python -c "from enhanced_database import init_enhanced_db; init_enhanced_db()"
```

## 🎯 Usage Guide

### Basic Search
1. Enter your mood or preferences in natural language
2. Select filters (genre, rating, year, platform)
3. Get AI-powered explanations and recommendations
4. Rate movies to improve future recommendations

### Advanced Features
- **Multilingual Search**: Search in Hindi, Telugu, Tamil, Spanish, etc.
- **Trending Discovery**: Find what's popular right now
- **Surprise Me**: Get unexpected recommendations
- **Watchlist Management**: Save titles for later
- **User Statistics**: Track your viewing preferences

### API Usage
```python
import requests

# Get recommendations
response = requests.post("http://localhost:8000/api/recommend", json={
    "query": "mind-bending sci-fi thrillers",
    "user_id": "demo_user",
    "genre": "Science Fiction",
    "min_rating": 7.0
})

# Rate a movie
requests.post("http://localhost:8000/api/interact", json={
    "user_id": "demo_user",
    "tmdb_id": 12345,
    "interaction_type": "like"
})
```

## 🔧 Configuration

### Environment Variables
| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key | Required |
| `TMDB_API_KEY` | TMDB API key | Required |
| `DATABASE_URL` | Database connection string | SQLite |
| `REDIS_URL` | Redis connection string | Optional |
| `DEBUG` | Debug mode | `true` |
| `MAX_RECOMMENDATIONS` | Max recommendations per request | `10` |

### Advanced Settings
- **Diversity Level**: Control recommendation diversity (0.0-1.0)
- **Explanation Style**: Choose AI explanation detail level
- **Language Preferences**: Set default language for responses
- **Caching**: Configure cache TTL and storage

## 🧪 Testing

### Unit Tests
```bash
cd backend
python -m pytest tests/
```

### Integration Tests
```bash
cd backend
python -m pytest tests/integration/
```

### Load Testing
```bash
cd backend
python -m pytest tests/load/
```

## 📈 Performance Optimization

### Database Optimization
- Indexing on frequently queried columns
- Query optimization and caching
- Connection pooling
- Database partitioning for large datasets

### AI Model Optimization
- Model quantization for faster inference
- Batch processing for multiple requests
- GPU acceleration when available
- Model caching and warm-up

### Caching Strategy
- Redis for session and recommendation caching
- In-memory caching for frequent queries
- CDN for static assets
- Database query result caching

## 🔒 Security

### API Security
- JWT token authentication
- Rate limiting and throttling
- Input validation and sanitization
- CORS configuration

### Data Security
- Encryption for sensitive data
- Secure API key management
- Database connection security
- Regular security audits

## 🐛 Troubleshooting

### Common Issues

#### Backend Won't Start
```bash
# Check if port 8000 is available
netstat -an | grep 8000

# Check Python dependencies
pip check

# Check logs
tail -f data/logs/backend.log
```

#### Frontend Connection Issues
```bash
# Check if backend is running
curl http://localhost:8000/api/health

# Check frontend logs
tail -f data/logs/frontend.log
```

#### Database Connection Issues
```bash
# Check database file permissions
ls -la mirai.db

# Reinitialize database
python -c "from enhanced_database import init_enhanced_db; init_enhanced_db()"
```

#### API Key Issues
```bash
# Verify API keys are set
echo $GEMINI_API_KEY
echo $TMDB_API_KEY

# Test API connectivity
curl -H "Authorization: Bearer YOUR_KEY" https://api.themoviedb.org/3/movie/popular
```

## 🤝 Contributing

### Development Setup
1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

### Code Style
- Follow PEP 8 for Python code
- Use TypeScript for frontend components
- Write comprehensive tests
- Document your code

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **TMDB**: For providing the amazing movie database API
- **Google**: For Gemini AI and language models
- **Hugging Face**: For transformer models and datasets
- **Streamlit**: For the beautiful frontend framework
- **FastAPI**: For the powerful backend framework

## 📞 Support

- 📧 Email: support@mirai-ai.com
- 💬 Discord: [Join our community](https://discord.gg/mirai-ai)
- 📚 Documentation: [Full docs](https://docs.mirai-ai.com)
- 🐛 Issues: [Report bugs](https://github.com/mirai-ai/movie-rec-project/issues)

---

**Made with ❤️ by the MIRAI AI Team**

{Colors.GREEN}🚀 Ready to revolutionize your movie discovery experience!{Colors.RESET}
"""
        
        try:
            with open(self.project_root / "README.md", 'w', encoding='utf-8') as f:
                f.write(readme_content)
            
            self.print_success("Enhanced README.md created")
            return True
            
        except Exception as e:
            self.print_error(f"Failed to create documentation: {str(e)}")
            return False
    
    def run_full_setup(self) -> bool:
        """Run the complete setup process"""
        self.print_banner()
        
        print(f"{Colors.PURPLE}{Colors.BOLD}Starting MIRAI AI Enhanced Setup...{Colors.RESET}")
        print()
        
        # Setup steps
        steps = [
            ("Python Version Check", self.check_python_version),
            ("Create Directories", self.create_directories),
            ("Create Virtual Environment", self.create_virtual_environment),
            ("Install Dependencies", self.install_dependencies),
            ("Create Environment File", self.create_environment_file),
            ("Create Setup Scripts", self.create_setup_script),
            ("Create Run Scripts", self.create_run_scripts),
            ("Create Documentation", self.create_documentation)
        ]
        
        success_count = 0
        total_steps = len(steps)
        
        for step_name, step_func in steps:
            print(f"{Colors.YELLOW}{Colors.BOLD}Step {success_count + 1}/{total_steps}: {step_name}{Colors.RESET}")
            
            if step_func():
                success_count += 1
                print(f"{Colors.GREEN}✅ {step_name} completed successfully{Colors.RESET}")
            else:
                print(f"{Colors.RED}❌ {step_name} failed{Colors.RESET}")
                self.print_warning("Continuing with setup despite failure...")
            
            print()
            time.sleep(1)  # Brief pause between steps
        
        # Final summary
        print(f"{Colors.PURPLE}{Colors.BOLD}╔══════════════════════════════════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.PURPLE}{Colors.BOLD}║{Colors.RESET} {Colors.GREEN if success_count == total_steps else Colors.YELLOW}Setup completed: {success_count}/{total_steps} steps successful{Colors.RESET} {Colors.PURPLE}{Colors.BOLD}║{Colors.RESET}")
        print(f"{Colors.PURPLE}{Colors.BOLD}╚══════════════════════════════════════════════════════════════════════════════╝{Colors.RESET}")
        print()
        
        if success_count == total_steps:
            print(f"{Colors.GREEN}{Colors.BOLD}🎉 MIRAI AI setup completed successfully!{Colors.RESET}")
            print()
            print(f"{Colors.CYAN}Next steps:{Colors.RESET}")
            print(f"1. {Colors.YELLOW}Add your API keys to the .env file{Colors.RESET}")
            print(f"2. {Colors.YELLOW}Run data collection: python backend/tmdb_data_collector.py{Colors.RESET}")
            print(f"3. {Colors.YELLOW}Start the application: {'run.bat' if self.os_type == 'Windows' else './run.sh'}{Colors.RESET}")
            print(f"4. {Colors.YELLOW}Visit http://localhost:8501 for the frontend{Colors.RESET}")
            print()
            print(f"{Colors.GREEN}🚀 Ready to revolutionize movie discovery!{Colors.RESET}")
            return True
        else:
            print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  Setup completed with some issues{Colors.RESET}")
            print(f"{Colors.CYAN}Please check the errors above and try again.{Colors.RESET}")
            return False

def main():
    """Main function"""
    setup = MIRAISetup()
    
    try:
        success = setup.run_full_setup()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.RED}Setup interrupted by user{Colors.RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error: {str(e)}{Colors.RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
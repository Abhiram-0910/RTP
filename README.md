# 🤖 MIRAI AI - Revolutionary Movie Recommendation Engine v2.0.0

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

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.8 or higher
- 8GB+ RAM recommended
- 10GB+ free disk space
- Internet connection for API calls

### 2. Setup and Run
```bash
# Run the automated setup
python final_setup.py

# Add your API keys to .env file:
# - GEMINI_API_KEY: Get from Google AI Studio
# - TMDB_API_KEY: Get from The Movie Database

# Start MIRAI AI
start_mirai.bat  # Windows
./start_mirai.sh  # Linux/Mac
```

### 3. Access Points
- **Frontend**: http://localhost:8501
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## 📋 API Keys Setup

### Google Gemini API
1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Add to `.env` file: `GEMINI_API_KEY=your_key_here`

### TMDB API
1. Visit [The Movie Database](https://www.themoviedb.org/settings/api)
2. Create an account and request API access
3. Add to `.env` file: `TMDB_API_KEY=your_key_here`

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

### Sample Queries
```
"Mind-bending movies that make you think"
"Feel-good comedies for a rainy day"
"Intense crime thrillers with plot twists"
"Beautiful animated films for adults"
"Inspiring true stories"
"कोई रोमांचक हिंदी फिल्म"
"తెలుగులో మంచి కామెడీ సినిమాలు"
```

## 🛠️ Advanced Configuration

### Environment Variables
| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Google Gemini API key | Required |
| `TMDB_API_KEY` | TMDB API key | Required |
| `DATABASE_URL` | Database connection string | SQLite |
| `DEBUG` | Debug mode | `true` |
| `MAX_RECOMMENDATIONS` | Max recommendations per request | `10` |
| `CACHE_TTL` | Cache TTL in seconds | `3600` |

### Database Options
```bash
# SQLite (default)
DATABASE_URL=sqlite:///./mirai.db

# PostgreSQL
DATABASE_URL=postgresql://user:password@localhost:5432/mirai

# MySQL
DATABASE_URL=mysql://user:password@localhost:3306/mirai
```

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
python -c "from working_database import init_enhanced_db; init_enhanced_db()"
```

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
python -c "from working_database import init_enhanced_db; init_enhanced_db()"
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

🚀 Ready to revolutionize your movie discovery experience!
# Movies and TV shows Recommendation Engine — Quick Start Guide

Follow these steps to get the Movies and TV shows Recommendation Engine recommendation engine running locally with the full AI RAG pipeline in place.

**Step 1: Prerequisites**
Ensure you have the following installed on your system:
- Python 3.10+
- Node.js 18+
- Docker (with Docker Compose)

**Step 2: Clone and set up .env files**
Copy the `backend/.env.example` file to create your local `.env` and fill in the required keys:
- `TMDB_API_KEY`
- `GEMINI_API_KEY`
- `DATABASE_URL` (Defaults to `postgresql+asyncpg://Movies and TV shows Recommendation Engine:Movies and TV shows Recommendation Engine_pass@localhost:5432/Movies and TV shows Recommendation Engine_db` if using Docker)
- `ENVIRONMENT`

**Step 3: Start the database container**
Starts a PostgreSQL instance with the pgvector extension enabled.
```bash
docker-compose up -d
```

**Step 4: Install Python dependencies**
```bash
pip install -r backend/requirements.txt
```

**Step 5: Collect TMDB Data and embeddings**
Run the data collector to populate your database with media items and embeddings. 
*(Warning: This process makes thousands of API requests, generates vector embeddings for each description, and takes about 15–30 minutes depending on connection speeds)*
```bash
python backend/tmdb_data_collector.py
```

**Step 6: Start the backend server**
Launch the FastAPI uvicorn engine locally.
```bash
uvicorn backend.enhanced_main:app --reload --port 8000
```

**Step 7: Set up the frontend client**
In a new terminal window, navigate to the frontend directory, install dependencies, and start the Vite dev server:
```bash
cd frontend-react
npm install
npm run dev
```

**Step 8: Access the application**
Open your web browser and navigate to:
[http://localhost:5173](http://localhost:5173)

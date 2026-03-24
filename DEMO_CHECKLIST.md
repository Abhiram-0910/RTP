# Movies and TV shows Recommendation Engine Live Demo Checklist

Follow these steps for a flawless 3-minute live demonstration:

1. **Open http://localhost:5173**
   - Show the elegant, responsive dark cinematic UI.

2. **Search: "something haunting with unexpected dark humor"**
   - Type query and hit enter.
   - Show results snapping in under 1.5s.
   - Wait ~1-2s for the background Gemini task to fade in the 8 per-card explanations magically. 

3. **Click "Deep Analysis"**
   - Show the LangChain RetrievalQA RAG panel streaming a deep, synthesized breakdown of the top recommended titles.

4. **Filter by "Netflix"**
   - Open the filters panel and select "Netflix".
   - Show that platforms strictly match only Netflix titles dynamically.

5. **Switch to Hindi**
   - Clear query, type: `Dil ko choo lene wali movie suggest karo`
   - Show how the backend detects the Hindi query automatically, translates it for the vector space, matches Hindi Bollywood / drama titles, and generates explanations entirely in Hindi.

6. **Similarity Factors Insight**
   - Click to expand any movie card.
   - Show the precise similarity factor bars (Mood, Genre, Theme, Rating), highlighting our transparent algorithmic breakdown.

7. **Satisfaction Feedback**
   - Scroll to the bottom and click the 👍 button.
   - Show the toast notification confirming the interaction was seamlessly recorded via `/api/interact`.

8. **Live Metrics View**
   - Open `http://localhost:8000/api/metrics` in the browser or terminal.
   - Show the real live payload logging tracking `total_searches`, `avg_response_ms`, and `user_satisfaction_rate`.

9. **Total DB Stats Check**
   - Open `http://localhost:8000/api/stats`.
   - Point out `total_titles` as the genuine count resulting from your ingestion scripts (e.g. 10K+ titles collected using TMDB).

10. **Proof of Performance**
    - Open `http://localhost:8000/api/benchmark`.
    - Run it to demonstrate `meets_target: true` and absolute latency figures for cold, warm, and cached paths.

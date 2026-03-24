from collections import deque
from threading import Lock

class MetricsTracker:
    def __init__(self):
        self._lock = Lock()
        self.total_searches = 0
        self.total_results = 0
        self.response_times = deque(maxlen=200)
        self.cache_hits = 0
        self.cache_misses = 0
        # Gemini metrics
        self.gemini_successes = 0
        self.gemini_failures = 0
        self.gemini_times = deque(maxlen=100)
        # Ollama metrics
        self.ollama_calls = 0
        self.ollama_successes = 0
        self.ollama_times = deque(maxlen=100)
        # Feedback
        self.satisfaction_positive = 0
        self.satisfaction_negative = 0

    def record_search(self, response_ms: float, result_count: int, cache_hit: bool):
        with self._lock:
            self.total_searches += 1
            self.total_results += result_count
            self.response_times.append(response_ms)
            if cache_hit: self.cache_hits += 1
            else: self.cache_misses += 1

    def record_gemini(self, success: bool, latency_ms: float):
        with self._lock:
            if success: self.gemini_successes += 1
            else: self.gemini_failures += 1
            self.gemini_times.append(latency_ms)

    def record_ollama(self, success: bool, latency_ms: float):
        with self._lock:
            self.ollama_calls += 1
            if success: self.ollama_successes += 1
            self.ollama_times.append(latency_ms)

    def record_satisfaction(self, positive: bool):
        with self._lock:
            if positive: self.satisfaction_positive += 1
            else: self.satisfaction_negative += 1

    def get_summary(self, db_stats: dict) -> dict:
        from backend.llm_router import llm_router  # lazy import to avoid circular
        times = list(self.response_times)
        g_times = list(self.gemini_times)
        o_times = list(self.ollama_times)
        total_feedback = self.satisfaction_positive + self.satisfaction_negative
        return {
            "total_searches": self.total_searches,
            "avg_response_ms": round(sum(times)/len(times), 1) if times else 0,
            "p95_response_ms": round(sorted(times)[int(len(times)*0.95)], 1) if len(times) > 20 else None,
            "cache_hit_rate": f"{self.cache_hits/(self.cache_hits+self.cache_misses)*100:.1f}%" if (self.cache_hits+self.cache_misses) > 0 else "0%",
            "gemini_success_rate": f"{self.gemini_successes/(self.gemini_successes+self.gemini_failures)*100:.1f}%" if (self.gemini_successes+self.gemini_failures) > 0 else "N/A",
            "gemini_avg_latency_ms": round(sum(g_times)/len(g_times), 1) if g_times else 0,
            "ollama_calls": self.ollama_calls,
            "ollama_avg_latency_ms": round(sum(o_times)/len(o_times), 1) if o_times else 0,
            "active_llm_provider": "ollama" if llm_router._gemini_in_cooldown() else "gemini",
            "user_satisfaction_rate": f"{self.satisfaction_positive/total_feedback*100:.1f}%" if total_feedback > 0 else "No feedback yet",
            "total_titles_indexed": db_stats.get("total_titles", 0),
            "total_chunks_indexed": db_stats.get("total_chunks", 0),
            "meets_3s_target": (sum(times)/len(times) < 3000) if times else False
        }

metrics = MetricsTracker()  # singleton

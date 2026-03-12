import requests
import pandas as pd
import time
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_fixed,
    before_sleep_log,
    RetryError,
)
import logging

logger = logging.getLogger(__name__)


class _RateLimitError(Exception):
    """
    Raised internally by ``_tmdb_get`` when TMDB returns HTTP 429.
    tenacity catches this class and applies the configured wait strategy.
    """
    def __init__(self, retry_after: float = 0.0):
        self.retry_after = retry_after
        super().__init__(f"TMDB rate-limited (Retry-After: {retry_after}s)")

class TMDBDataCollector:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.themoviedb.org/3"
        self.image_base_url = "https://image.tmdb.org/t/p/w500"

    # ── Core HTTP helper ─────────────────────────────────────────────────────

    @staticmethod
    def _retry_wait(retry_state) -> float:
        """
        Custom tenacity wait function.

        If the last exception was a ``_RateLimitError`` and TMDB supplied a
        ``Retry-After`` header, sleep for exactly that many seconds.
        Otherwise fall back to full-jitter exponential backoff (1-60 s).
        """
        exc = retry_state.outcome.exception()
        if isinstance(exc, _RateLimitError) and exc.retry_after > 0:
            print(f"[TMDB] Rate limited. Honouring Retry-After: {exc.retry_after}s")
            return exc.retry_after
        # Exponential backoff: 2^attempt seconds, capped at 60, with jitter
        exp = wait_exponential(multiplier=1, min=2, max=60)
        return exp(retry_state)

    def _tmdb_get(self, url: str, params: dict) -> requests.Response:
        """
        Central GET helper with tenacity-powered retry logic.

        Retry policy
        ------------
        * Catches only ``_RateLimitError`` (HTTP 429) and transient network
          errors (``requests.exceptions.RequestException``).
        * Up to 6 attempts total.
        * Wait time: ``Retry-After`` header value when present, else
          exponential backoff (2-60 s).
        * Raises ``RetryError`` after exhausting all attempts.
        """
        @retry(
            retry=retry_if_exception_type((_RateLimitError, requests.exceptions.RequestException)),
            stop=stop_after_attempt(6),
            wait=self._retry_wait,
            reraise=False,
            before_sleep=before_sleep_log(logger, logging.WARNING),
        )
        def _get() -> requests.Response:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 429:
                # Parse Retry-After if available (TMDB sends it as an integer)
                retry_after = float(resp.headers.get("Retry-After", 0))
                raise _RateLimitError(retry_after=retry_after)
            return resp

        return _get()

    def get_trending_movies(self, time_window: str = "week", page: int = 1) -> List[Dict]:
        """Get trending movies from TMDB."""
        url = f"{self.base_url}/trending/movie/{time_window}"
        params = {"api_key": self.api_key, "page": page}
        try:
            resp = self._tmdb_get(url, params)
            if resp.status_code == 200:
                return resp.json().get("results", [])
            print(f"Error fetching trending movies: {resp.status_code}")
        except Exception as exc:
            print(f"Exception in get_trending_movies: {exc}")
        return []

    def get_trending_tv_shows(self, time_window: str = "week", page: int = 1) -> List[Dict]:
        """Get trending TV shows from TMDB."""
        url = f"{self.base_url}/trending/tv/{time_window}"
        params = {"api_key": self.api_key, "page": page}
        try:
            resp = self._tmdb_get(url, params)
            if resp.status_code == 200:
                return resp.json().get("results", [])
            print(f"Error fetching trending TV shows: {resp.status_code}")
        except Exception as exc:
            print(f"Exception in get_trending_tv_shows: {exc}")
        return []

    def get_movie_details(self, movie_id: int, language: str = "en-US") -> Optional[Dict]:
        """Get detailed movie information, optionally in a TMDB-supported locale."""
        url = f"{self.base_url}/movie/{movie_id}"
        params = {
            "api_key": self.api_key,
            "language": language,
            "append_to_response": "credits,keywords,watch/providers",
        }
        try:
            resp = self._tmdb_get(url, params)
            if resp.status_code == 200:
                return resp.json()
            print(f"Error fetching movie details for {movie_id}: {resp.status_code}")
        except Exception as exc:
            print(f"Exception in get_movie_details({movie_id}): {exc}")
        return None

    def get_tv_show_details(self, tv_id: int, language: str = "en-US") -> Optional[Dict]:
        """Get detailed TV show information, optionally in a TMDB-supported locale."""
        url = f"{self.base_url}/tv/{tv_id}"
        params = {
            "api_key": self.api_key,
            "language": language,
            "append_to_response": "credits,keywords,watch/providers",
        }
        try:
            resp = self._tmdb_get(url, params)
            if resp.status_code == 200:
                return resp.json()
            print(f"Error fetching TV show details for {tv_id}: {resp.status_code}")
        except Exception as exc:
            print(f"Exception in get_tv_show_details({tv_id}): {exc}")
        return None

    def get_localized_overlay(
        self,
        tmdb_id: int,
        media_type: str,
        language: str,
    ) -> Dict[str, str]:
        """
        Fetch **only** the localized title and overview for a given TMDB ID and
        locale — a single lightweight API call that avoids duplicating the full
        credits/keywords payload.

        Returns a dict ``{"title": ..., "overview": ...}`` with the localized
        strings, or empty strings if TMDB does not have a translation.

        Design note
        -----------
        TMDB stores canonical technical metadata (cast, crew, keywords, providers)
        independent of locale, so we fetch those once in English and only
        overlay ``title`` and ``overview`` per locale.  This keeps the total
        number of API calls at::

            (1 English detail + N locales) per title

        instead of the naive (N locales × full detail) approach.
        """
        endpoint = "movie" if media_type == "movie" else "tv"
        url = f"{self.base_url}/{endpoint}/{tmdb_id}"
        params = {"api_key": self.api_key, "language": language}
        try:
            resp = self._tmdb_get(url, params)
            if resp.status_code == 200:
                data = resp.json()
                # TV uses 'name', movies use 'title'
                title    = data.get("title") or data.get("name") or ""
                overview = data.get("overview") or ""
                return {"title": title, "overview": overview}
        except Exception as exc:
            logger.warning(
                "[Locale] Could not fetch %s overlay for id=%s lang=%s: %s",
                media_type, tmdb_id, language, exc,
            )
        return {"title": "", "overview": ""}

    def discover_movies(self, page: int = 1, year_min: int = 2000, vote_min: float = 6.0) -> List[Dict]:
        """Discover movies based on criteria."""
        url = f"{self.base_url}/discover/movie"
        params = {
            "api_key": self.api_key,
            "page": page,
            "primary_release_date.gte": f"{year_min}-01-01",
            "vote_average.gte": vote_min,
            "sort_by": "popularity.desc",
            "with_original_language": "en,hi,te,ta,es,fr,de,it,ja,ko,zh",
        }
        try:
            resp = self._tmdb_get(url, params)
            if resp.status_code == 200:
                return resp.json().get("results", [])
            print(f"Error discovering movies: {resp.status_code}")
        except Exception as exc:
            print(f"Exception in discover_movies: {exc}")
        return []

    def discover_tv_shows(self, page: int = 1, year_min: int = 2000, vote_min: float = 6.0) -> List[Dict]:
        """Discover TV shows based on criteria."""
        url = f"{self.base_url}/discover/tv"
        params = {
            "api_key": self.api_key,
            "page": page,
            "first_air_date.gte": f"{year_min}-01-01",
            "vote_average.gte": vote_min,
            "sort_by": "popularity.desc",
            "with_original_language": "en,hi,te,ta,es,fr,de,it,ja,ko,zh",
        }
        try:
            resp = self._tmdb_get(url, params)
            if resp.status_code == 200:
                return resp.json().get("results", [])
            print(f"Error discovering TV shows: {resp.status_code}")
        except Exception as exc:
            print(f"Exception in discover_tv_shows: {exc}")
        return []

    def extract_genres(self, genres: List[Dict]) -> List[str]:
        """Extract genre names from genre objects"""
        return [genre["name"] for genre in genres if "name" in genre]
    
    def extract_cast(self, credits: Dict, limit: int = 5) -> List[str]:
        """Extract main cast members"""
        cast = credits.get("cast", [])[:limit]
        return [actor["name"] for actor in cast if "name" in actor]
    
    def extract_director(self, credits: Dict) -> Optional[str]:
        """Extract director name from credits"""
        crew = credits.get("crew", [])
        directors = [person["name"] for person in crew if person.get("job") == "Director"]
        return directors[0] if directors else None
    
    def extract_streaming_platforms(self, watch_providers: Dict, region: str = "US") -> List[str]:
        """Extract available streaming platforms"""
        platforms = []
        if "results" in watch_providers and region in watch_providers["results"]:
            region_data = watch_providers["results"][region]
            
            # Get flatrate (subscription) services
            if "flatrate" in region_data:
                platforms.extend([provider["provider_name"] for provider in region_data["flatrate"]])
            
            # Get free services
            if "free" in region_data:
                platforms.extend([provider["provider_name"] for provider in region_data["free"]])
            
            # Get rental services (if no subscription available)
            if not platforms and "rent" in region_data:
                platforms.extend([provider["provider_name"] for provider in region_data["rent"]])
        
        return list(set(platforms))  # Remove duplicates
    
    def process_movie_data(
        self,
        movie_data: Dict,
        locale: str = "en-US",
        localized_data: Optional[Dict[str, str]] = None,
    ) -> Dict:
        """
        Process raw movie data into a standardised row.

        Parameters
        ----------
        movie_data      : Full TMDB movie detail response (English).
        locale          : BCP-47 locale tag for this row (e.g. ``"hi-IN"``).
        localized_data  : Dict with ``title`` and ``overview`` from the locale
                          overlay call.  Falls back to the English values when
                          the localized strings are empty.
        """
        loc = localized_data or {}
        en_title    = movie_data.get("title", "")
        en_overview = movie_data.get("overview", "")
        return {
            "id":                  movie_data.get("id"),
            "tmdb_id":             movie_data.get("id"),
            "title":               loc.get("title") or en_title,
            "title_en":            en_title,
            "overview":            loc.get("overview") or en_overview,
            "overview_en":         en_overview,
            "locale":              locale,
            "release_date":        movie_data.get("release_date", ""),
            "rating":              movie_data.get("vote_average", 0.0),
            "poster_path":         movie_data.get("poster_path", ""),
            "media_type":          "movie",
            "original_language":   movie_data.get("original_language", "en"),
            "runtime":             movie_data.get("runtime"),
            "budget":              movie_data.get("budget"),
            "revenue":             movie_data.get("revenue"),
            "status":              movie_data.get("status", "released"),
            "tagline":             movie_data.get("tagline", ""),
            "genres":              self.extract_genres(movie_data.get("genres", [])),
            "cast":                self.extract_cast(movie_data.get("credits", {})),
            "director":            self.extract_director(movie_data.get("credits", {})),
            "streaming_platforms": self.extract_streaming_platforms(movie_data.get("watch/providers", {})),
            "popularity":          movie_data.get("popularity", 0.0),
            "imdb_id":             movie_data.get("imdb_id", ""),
            "keywords":            [kw["name"] for kw in movie_data.get("keywords", {}).get("keywords", [])],
        }
    
    def process_tv_show_data(
        self,
        tv_data: Dict,
        locale: str = "en-US",
        localized_data: Optional[Dict[str, str]] = None,
    ) -> Dict:
        """
        Process raw TV show data into a standardised row.

        Parameters
        ----------
        tv_data         : Full TMDB TV detail response (English).
        locale          : BCP-47 locale tag for this row (e.g. ``"te-IN"``).
        localized_data  : Dict with ``title`` and ``overview`` from the locale
                          overlay call.  Falls back to the English values when
                          the localized strings are empty.
        """
        loc = localized_data or {}
        en_title    = tv_data.get("name", "")
        en_overview = tv_data.get("overview", "")
        return {
            "id":                   tv_data.get("id"),
            "tmdb_id":              tv_data.get("id"),
            "title":                loc.get("title") or en_title,
            "title_en":             en_title,
            "overview":             loc.get("overview") or en_overview,
            "overview_en":          en_overview,
            "locale":               locale,
            "release_date":         tv_data.get("first_air_date", ""),
            "rating":               tv_data.get("vote_average", 0.0),
            "poster_path":          tv_data.get("poster_path", ""),
            "media_type":           "tv",
            "original_language":    tv_data.get("original_language", "en"),
            "runtime":              tv_data.get("episode_run_time", [None])[0] if tv_data.get("episode_run_time") else None,
            "status":               tv_data.get("status", "released"),
            "tagline":              tv_data.get("tagline", ""),
            "genres":               self.extract_genres(tv_data.get("genres", [])),
            "cast":                 self.extract_cast(tv_data.get("credits", {})),
            "director":             self.extract_director(tv_data.get("credits", {})),
            "streaming_platforms":  self.extract_streaming_platforms(tv_data.get("watch/providers", {})),
            "popularity":           tv_data.get("popularity", 0.0),
            "number_of_seasons":    tv_data.get("number_of_seasons"),
            "number_of_episodes":   tv_data.get("number_of_episodes"),
            "keywords":             [kw["name"] for kw in tv_data.get("keywords", {}).get("results", [])],
        }
    
    def collect_comprehensive_dataset(
        self,
        target_size: int = 10000,
        batch_size: int = 20,
        locales: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Collect a multilingual dataset of movies and TV shows.

        For each unique TMDB title found:
        1. Fetch full English details once (credits, keywords, providers).
        2. For every locale in *locales*, call ``get_localized_overlay`` to get
           the translated title and overview in a single lightweight API call.
        3. Produce one row per ``(tmdb_id, locale)`` in the output DataFrame.

        The output DataFrame contains:
        - ``title`` / ``overview``     — in the row's locale (falls back to English
          when TMDB has no translation).
        - ``title_en`` / ``overview_en``  — always the English original.
        - ``locale``                   — BCP-47 locale tag ("en-US", "hi-IN", "te-IN").

        Parameters
        ----------
        target_size : Maximum rows **per locale** to keep (sorted by popularity).
        locales     : List of BCP-47 locale strings to collect.
                      Default: ``["en-US", "hi-IN", "te-IN"]``.
        """
        if locales is None:
            locales = ["en-US", "hi-IN", "te-IN"]

        all_media: list = []

        print(f"Starting multilingual data collection for locales: {locales}")
        print(f"Targeting {target_size} rows per locale → ~{target_size * len(locales)} total rows.")

        # ── Step 1: Discover unique TMDB IDs (locale-independent) ────────────
        print("\n[1/3] Collecting trending content IDs...")
        trending_movie_ids: set = set()
        trending_tv_ids:    set = set()

        for page in range(1, 6):
            for m in self.get_trending_movies("week", page):
                trending_movie_ids.add(m["id"])
            for t in self.get_trending_tv_shows("week", page):
                trending_tv_ids.add(t["id"])

        print(f"    {len(trending_movie_ids)} trending movies, {len(trending_tv_ids)} trending TV shows.")

        print("[1/3] Discovering high-rated content...")
        discovered_movie_ids: set = set()
        discovered_tv_ids:    set = set()

        for page in range(1, 21):
            for m in self.discover_movies(page, year_min=2010, vote_min=7.0):
                discovered_movie_ids.add(m["id"])
            for t in self.discover_tv_shows(page, year_min=2010, vote_min=7.0):
                discovered_tv_ids.add(t["id"])
            if page % 5 == 0:
                print(f"    Completed {page}/20 discovery pages...")

        all_movie_ids = list(trending_movie_ids | discovered_movie_ids)
        all_tv_ids    = list(trending_tv_ids    | discovered_tv_ids)
        print(f"    {len(all_movie_ids)} unique movies, {len(all_tv_ids)} unique TV shows.")

        # ── Step 2: Fetch full English details once per ID ────────────────────
        print("\n[2/3] Fetching full English details (credits, keywords, providers)...")

        # English base detail cache: tmdb_id -> raw TMDB response
        movie_details_cache: dict = {}
        tv_details_cache:    dict = {}

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self.get_movie_details, mid, "en-US"): mid
                for mid in all_movie_ids[:5000]
            }
            for future in as_completed(futures):
                data = future.result()
                if (
                    data
                    and data.get("overview")
                    and data.get("vote_average", 0) > 5.0
                ):
                    movie_details_cache[data["id"]] = data

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self.get_tv_show_details, tid, "en-US"): tid
                for tid in all_tv_ids[:5000]
            }
            for future in as_completed(futures):
                data = future.result()
                if (
                    data
                    and data.get("overview")
                    and data.get("vote_average", 0) > 5.0
                ):
                    tv_details_cache[data["id"]] = data

        print(
            f"    Cached {len(movie_details_cache)} movies and "
            f"{len(tv_details_cache)} TV shows in English."
        )

        # ── Step 3: For each locale, overlay title+overview and build rows ─────
        print("\n[3/3] Generating localized rows...")

        locale_frames: list = []

        for locale in locales:
            print(f"\n  Locale: {locale}")
            locale_rows: list = []

            # Movies
            def _fetch_movie_locale(mid_data, _locale=locale):
                mid, en_data = mid_data
                if _locale == "en-US":
                    overlay = {
                        "title":    en_data.get("title", ""),
                        "overview": en_data.get("overview", ""),
                    }
                else:
                    overlay = self.get_localized_overlay(mid, "movie", _locale)
                return self.process_movie_data(en_data, locale=_locale, localized_data=overlay)

            with ThreadPoolExecutor(max_workers=5) as executor:
                m_futures = [
                    executor.submit(_fetch_movie_locale, item)
                    for item in movie_details_cache.items()
                ]
                for future in as_completed(m_futures):
                    result = future.result()
                    if result:
                        locale_rows.append(result)

            # TV shows
            def _fetch_tv_locale(tid_data, _locale=locale):
                tid, en_data = tid_data
                if _locale == "en-US":
                    overlay = {
                        "title":    en_data.get("name", ""),
                        "overview": en_data.get("overview", ""),
                    }
                else:
                    overlay = self.get_localized_overlay(tid, "tv", _locale)
                return self.process_tv_show_data(en_data, locale=_locale, localized_data=overlay)

            with ThreadPoolExecutor(max_workers=5) as executor:
                t_futures = [
                    executor.submit(_fetch_tv_locale, item)
                    for item in tv_details_cache.items()
                ]
                for future in as_completed(t_futures):
                    result = future.result()
                    if result:
                        locale_rows.append(result)

            # Sort and cap per locale
            locale_df = pd.DataFrame(locale_rows)
            if not locale_df.empty:
                locale_df["popularity_score"] = locale_df["popularity"].fillna(0)
                locale_df = locale_df.sort_values(
                    ["popularity_score", "rating"], ascending=[False, False]
                )
                if len(locale_df) > target_size:
                    locale_df = locale_df.head(target_size)

            print(f"    {len(locale_df)} rows for locale '{locale}'.")
            locale_frames.append(locale_df)

        # ── Combine all locales ────────────────────────────────────────────────
        df = pd.concat(locale_frames, ignore_index=True) if locale_frames else pd.DataFrame()
        df["trending_score"] = 0.0
        df["last_updated"]   = datetime.utcnow()

        print(f"\nFinal multilingual dataset: {len(df)} rows across {len(locales)} locales.")
        return df


    def save_dataset(self, df: pd.DataFrame, output_path: str = "../data/enhanced_dataset.csv"):
        """Save the collected multilingual dataset to CSV files."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"Dataset saved to {output_path}")

        # Per-media-type splits
        movies_df = df[df["media_type"] == "movie"]
        tv_df     = df[df["media_type"] == "tv"]
        movies_df.to_csv("../data/enhanced_movies.csv", index=False)
        tv_df.to_csv("../data/enhanced_tv_shows.csv", index=False)
        print(f"Saved {len(movies_df)} movie rows and {len(tv_df)} TV show rows.")

        # Per-locale splits (useful for locale-specific ingestion)
        if "locale" in df.columns:
            for locale in df["locale"].unique():
                locale_path = os.path.join(
                    os.path.dirname(output_path),
                    f"enhanced_dataset_{locale.replace('-', '_')}.csv",
                )
                df[df["locale"] == locale].to_csv(locale_path, index=False)
            print(f"Saved per-locale CSV files for: {list(df['locale'].unique())}")

def main():
    """Main function to collect comprehensive dataset"""
    api_key = os.getenv("TMDB_API_KEY")
    if not api_key:
        print("Please set TMDB_API_KEY environment variable")
        return
    
    collector = TMDBDataCollector(api_key)
    
    # Collect comprehensive dataset
    df = collector.collect_comprehensive_dataset(target_size=12000)
    
    # Save the dataset
    collector.save_dataset(df)
    
    # Print statistics
    print("\nDataset Statistics:")
    print(f"Total titles: {len(df)}")
    print(f"Movies: {len(df[df['media_type'] == 'movie'])}")
    print(f"TV Shows: {len(df[df['media_type'] == 'tv'])}")
    print(f"Average rating: {df['rating'].mean():.2f}")
    print(f"Languages: {df['original_language'].nunique()}")
    print(f"Streaming platforms found: {df['streaming_platforms'].apply(lambda x: len(x) if isinstance(x, list) else 0).sum()}")

if __name__ == "__main__":
    main()
"""
tests/evaluation.py — Offline recommender evaluation: MAP@10 and NDCG@10

Usage
-----
    cd c:/Projects/RTP
    python tests/evaluation.py                          # uses DATABASE_URL from .env
    python tests/evaluation.py --users 50 --k 10       # override defaults
    python tests/evaluation.py --threshold 0.80        # custom pass threshold

What it does
------------
1. Loads user_interactions from the PostgreSQL database (via DATABASE_URL).
2. For each user with at least MIN_INTERACTIONS interactions, sorts by
   timestamp, then masks the last 20 % as "future" ground-truth items.
3. Calls AdvancedRecommendationEngine with the remaining "past" interactions.
4. Computes MAP@K and NDCG@K by comparing the engine's ranked list against the
   held-out ground-truth set.
5. Prints a formatted console report and exits with code 1 if either metric
   falls below the configured threshold (default 0.85) so CI pipelines can
   catch regressions.

Requires
--------
    DATABASE_URL in .env (same format used by the main app)
    pip install sqlalchemy psycopg2-binary python-dotenv numpy
"""

import argparse
import math
import os
import sys
from collections import defaultdict
from textwrap import dedent

import numpy as np
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# ── Path setup ─────────────────────────────────────────────────────────────────
# Allow importing backend modules when the script is run from the repo root.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.advanced_recommendation_engine import AdvancedRecommendationEngine

# ── Constants ──────────────────────────────────────────────────────────────────
K_DEFAULT          = 10      # rank cutoff
MIN_INTERACTIONS   = 5       # users with fewer interactions are skipped
TEST_SPLIT_RATIO   = 0.20    # hold out last 20 % as ground truth
SUCCESS_THRESHOLD  = 0.85    # target claimed in the README


# ══════════════════════════════════════════════════════════════════════════════
# Data loading
# ══════════════════════════════════════════════════════════════════════════════

def load_interactions(database_url: str) -> dict[str, list[dict]]:
    """
    Return a dict mapping ``user_id → [interaction dicts sorted by timestamp]``.

    Each interaction dict has at least ``tmdb_id`` and ``created_at`` (or
    ``timestamp`` — whichever column exists in the schema).
    """
    engine = create_engine(database_url)
    with engine.connect() as conn:
        # Accept either 'created_at' or 'timestamp' as the time column.
        try:
            rows = conn.execute(
                text(
                    "SELECT user_id, tmdb_id, created_at AS ts, "
                    "       rating, interaction_type "
                    "FROM   user_interactions "
                    "ORDER  BY user_id, created_at ASC"
                )
            ).fetchall()
        except Exception:
            rows = conn.execute(
                text(
                    "SELECT user_id, tmdb_id, timestamp AS ts, "
                    "       rating, interaction_type "
                    "FROM   user_interactions "
                    "ORDER  BY user_id, timestamp ASC"
                )
            ).fetchall()

    interactions: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        interactions[str(row.user_id)].append({
            "tmdb_id":          str(row.tmdb_id),
            "ts":               row.ts,
            "rating":           float(row.rating) if row.rating else 1.0,
            "interaction_type": row.interaction_type,
        })

    return dict(interactions)


def load_item_features(database_url: str) -> dict[str, dict]:
    """Return a lightweight tmdb_id → {title, genres, ...} map for the engine."""
    engine = create_engine(database_url)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT tmdb_id, title, genres, overview FROM media LIMIT 50000")
        ).fetchall()

    return {
        str(r.tmdb_id): {
            "id":       str(r.tmdb_id),
            "title":    r.title or "",
            "genres":   r.genres or [],
            "overview": r.overview or "",
        }
        for r in rows
    }


# ══════════════════════════════════════════════════════════════════════════════
# Train / test split
# ══════════════════════════════════════════════════════════════════════════════

def split_user_interactions(
    interactions: dict[str, list[dict]],
    test_ratio:   float = TEST_SPLIT_RATIO,
    min_count:    int   = MIN_INTERACTIONS,
) -> tuple[dict, dict]:
    """
    For each eligible user, split their interaction history into:
    - ``train`` : chronologically first (1 - test_ratio) interactions
    - ``test``  : chronologically last  test_ratio interactions (ground truth)

    Users with fewer than *min_count* interactions are excluded.

    Returns
    -------
    train_interactions, test_interactions  — same dict format as input.
    """
    train: dict[str, list[dict]] = {}
    test:  dict[str, list[dict]] = {}

    for user_id, history in interactions.items():
        if len(history) < min_count:
            continue
        cutoff = max(1, math.ceil(len(history) * (1.0 - test_ratio)))
        train[user_id] = history[:cutoff]
        test[user_id]  = history[cutoff:]

    return train, test


# ══════════════════════════════════════════════════════════════════════════════
# Metric calculations
# ══════════════════════════════════════════════════════════════════════════════

def average_precision_at_k(
    ranked_ids: list[str],
    relevant:   set[str],
    k:          int,
) -> float:
    """AP@K for a single user."""
    if not relevant:
        return 0.0

    hits        = 0
    precision_sum = 0.0

    for rank, item_id in enumerate(ranked_ids[:k], start=1):
        if item_id in relevant:
            hits += 1
            precision_sum += hits / rank

    return precision_sum / min(len(relevant), k)


def ndcg_at_k(
    ranked_ids: list[str],
    relevant:   set[str],
    k:          int,
) -> float:
    """NDCG@K for a single user (binary relevance)."""
    if not relevant:
        return 0.0

    # Discounted Cumulative Gain of the predicted list
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, item_id in enumerate(ranked_ids[:k], start=1)
        if item_id in relevant
    )

    # Ideal DCG: all relevant items at the top
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))

    return dcg / idcg if idcg > 0 else 0.0


# ══════════════════════════════════════════════════════════════════════════════
# Recommendation query
# ══════════════════════════════════════════════════════════════════════════════

def get_recommendations(
    engine:            AdvancedRecommendationEngine,
    user_id:           str,
    train_history:     list[dict],
    item_features:     dict[str, dict],
    all_candidate_ids: list[str],
    k:                 int,
) -> list[str]:
    """
    Query the AdvancedRecommendationEngine for *user_id* and return the top-K
    recommended TMDB IDs.

    We build a synthetic zero-vector query embedding (the collaborative and
    trending scores do not need a real text query) so the evaluation is driven
    purely by the collaborative-filtering signal — a fair offline test.
    """
    # Exclude items the user has already seen
    seen = {i["tmdb_id"] for i in train_history}
    candidates = [
        item_features[iid]
        for iid in all_candidate_ids
        if iid not in seen and iid in item_features
    ]

    if not candidates:
        return []

    # Zero-vector: same dimension as Gemini (768) or HF (384) — engine handles mismatch
    zero_query = np.zeros(768, dtype=float).tolist()

    try:
        scored = engine.hybrid_content_collaborative_scoring(
            query_embedding   = zero_query,
            user_id           = user_id,
            candidate_items   = candidates[:200],   # cap for speed
            user_interactions = train_history,
            item_features     = item_features,
        )
        return [str(item.get("id") or item.get("tmdb_id", "")) for item in scored[:k]]
    except Exception as exc:
        print(f"  [WARN] Engine error for user {user_id}: {exc}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# Report
# ══════════════════════════════════════════════════════════════════════════════

def print_report(
    map_score:  float,
    ndcg_score: float,
    n_users:    int,
    k:          int,
    threshold:  float,
) -> bool:
    """Print a formatted console report. Returns True if both metrics pass."""
    passed_map  = map_score  >= threshold
    passed_ndcg = ndcg_score >= threshold
    passed      = passed_map and passed_ndcg

    sep    = "═" * 60
    status = lambda ok: "✅  PASS" if ok else "❌  FAIL"

    print(f"\n{sep}")
    print("  MIRAI Recommendation Engine — Offline Evaluation Report")
    print(sep)
    print(f"  Users evaluated  : {n_users}")
    print(f"  Rank cutoff (K)  : {k}")
    print(f"  Success threshold: {threshold:.0%}")
    print(sep)
    print(f"  MAP@{k:<3}  : {map_score:6.2%}    {status(passed_map)}")
    print(f"  NDCG@{k:<2}  : {ndcg_score:6.2%}    {status(passed_ndcg)}")
    print(sep)

    if passed:
        print("  Overall: ✅  BOTH METRICS PASS  — engine meets the 85 % target.")
    else:
        print("  Overall: ❌  ONE OR MORE METRICS BELOW THRESHOLD.")
        if not passed_map:
            gap = threshold - map_score
            print(f"           MAP@{k} is {gap:.2%} below target.")
        if not passed_ndcg:
            gap = threshold - ndcg_score
            print(f"           NDCG@{k} is {gap:.2%} below target.")

    print(sep + "\n")
    return passed


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description=dedent("""\
            Offline evaluation of AdvancedRecommendationEngine.
            Measures MAP@K and NDCG@K against held-out user interactions.
        """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--k",         type=int,   default=K_DEFAULT,         help=f"Rank cutoff (default {K_DEFAULT})")
    parser.add_argument("--users",     type=int,   default=200,               help="Max users to evaluate (default 200)")
    parser.add_argument("--threshold", type=float, default=SUCCESS_THRESHOLD, help=f"Pass threshold 0-1 (default {SUCCESS_THRESHOLD})")
    parser.add_argument("--database-url", default=None,                       help="Override DATABASE_URL from .env")
    args = parser.parse_args()

    database_url = args.database_url or os.getenv("DATABASE_URL")
    if not database_url:
        print("[ERROR] DATABASE_URL not set. Add it to .env or pass --database-url.")
        sys.exit(1)

    k         = args.k
    threshold = args.threshold
    max_users = args.users

    # ── 1. Load data ───────────────────────────────────────────────────────
    print("Loading user interactions from database…")
    all_interactions = load_interactions(database_url)
    print(f"  {len(all_interactions)} users found in user_interactions.")

    print("Loading item features from media table…")
    item_features = load_item_features(database_url)
    all_candidate_ids = list(item_features.keys())
    print(f"  {len(item_features)} items available as candidates.")

    # ── 2. Train/test split ────────────────────────────────────────────────
    train_interactions, test_interactions = split_user_interactions(
        all_interactions, test_ratio=TEST_SPLIT_RATIO, min_count=MIN_INTERACTIONS
    )
    eval_users = list(train_interactions.keys())[:max_users]
    print(f"\nEvaluating {len(eval_users)} users (of {len(train_interactions)} eligible)…")

    if not eval_users:
        print("[ERROR] No users with sufficient interaction history. Exiting.")
        sys.exit(1)

    # ── 3. Set up engine (no embedding model needed for collab-only eval) ──
    rec_engine = AdvancedRecommendationEngine(embeddings_model=None)

    # ── 4. Compute metrics per user ────────────────────────────────────────
    ap_scores:   list[float] = []
    ndcg_scores: list[float] = []
    skipped = 0

    for i, user_id in enumerate(eval_users, 1):
        train_hist = train_interactions[user_id]
        test_hist  = test_interactions.get(user_id, [])

        if not test_hist:
            skipped += 1
            continue

        ground_truth = {item["tmdb_id"] for item in test_hist}

        ranked = get_recommendations(
            engine            = rec_engine,
            user_id           = user_id,
            train_history     = train_hist,
            item_features     = item_features,
            all_candidate_ids = all_candidate_ids,
            k                 = k,
        )

        ap   = average_precision_at_k(ranked, ground_truth, k)
        ndcg = ndcg_at_k(ranked, ground_truth, k)

        ap_scores.append(ap)
        ndcg_scores.append(ndcg)

        if i % 25 == 0:
            print(
                f"  [{i}/{len(eval_users)}] "
                f"running MAP@{k}={np.mean(ap_scores):.3f}  "
                f"NDCG@{k}={np.mean(ndcg_scores):.3f}"
            )

    n_evaluated = len(ap_scores)
    if n_evaluated == 0:
        print("[ERROR] No users could be evaluated — all had empty test sets.")
        sys.exit(1)

    if skipped:
        print(f"  (Skipped {skipped} users with empty test sets.)")

    # ── 5. Print report ────────────────────────────────────────────────────
    final_map  = float(np.mean(ap_scores))
    final_ndcg = float(np.mean(ndcg_scores))

    passed = print_report(
        map_score  = final_map,
        ndcg_score = final_ndcg,
        n_users    = n_evaluated,
        k          = k,
        threshold  = threshold,
    )

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()

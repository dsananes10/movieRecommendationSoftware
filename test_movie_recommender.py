"""
test_movie_recommender.py

Flexible tester for movie_recommender.Recommender.
This version:
  - DOES NOT create files.
  - DOES NOT hardcode filenames.
  - Takes user-provided --movies and --ratings file paths.
  - Automatically checks validity, detects errors, and prints diagnostics.

Usage:
    python test_movie_recommender.py --movies data/mv_clean_small.txt --ratings data/rt_clean_small.txt
"""
from __future__ import annotations

import sys
from typing import Optional, Tuple, List

from movie_recommender import Recommender


def banner(msg: str) -> None:
    print("\n" + "=" * 70)
    print(msg)
    print("=" * 70)


def parse_args(argv: List[str]) -> Tuple[Optional[str], Optional[str]]:
    movies_path = None
    ratings_path = None
    i = 0
    while i < len(argv):
        if argv[i] == "--movies" and i + 1 < len(argv):
            movies_path = argv[i + 1]
            i += 2
        elif argv[i] == "--ratings" and i + 1 < len(argv):
            ratings_path = argv[i + 1]
            i += 2
        else:
            i += 1
    return movies_path, ratings_path


def classify_validity(stats: dict) -> str:
    """Classify input pair as Valid / Erroneous based on skip counts."""
    # any nonzero skip count means something was malformed, duplicate, etc.
    problem_keys = [k for k, v in stats.items() if "skipped" in k and v > 0]
    if problem_keys:
        return f"❌ Erroneous input detected ({len(problem_keys)} issues)"
    else:
        return "✅ Valid input (no problems detected)"


def run_test(movies_path: str, ratings_path: str) -> None:
    banner("RUNNING TEST")
    print("Movies file:", movies_path)
    print("Ratings file:", ratings_path)

    engine = Recommender()
    engine.load_movies(movies_path)
    engine.load_ratings(ratings_path)

    # --- Summary of what was loaded / skipped ---
    print("\n--- Load Statistics ---")
    for k in sorted(engine.load_stats.keys()):
        print(f"{k:35s} {engine.load_stats[k]}")

    verdict = classify_validity(engine.load_stats)
    print("\nOverall verdict:", verdict)

    # --- Quick sanity checks ---
    movies_loaded = len(engine.movies_by_id)
    ratings_loaded = len(engine.ratings)
    print(f"\nMovies successfully loaded: {movies_loaded}")
    print(f"Ratings successfully loaded: {ratings_loaded}")

    # If data loaded, try a few features safely
    if ratings_loaded > 0:
        print("\nTop 3 movies:")
        for row in engine.top_n_movies(3):
            print("  ", row)

        print("\nTop 2 genres:")
        for row in engine.top_n_genres(2):
            print("  ", row)

        uids = engine.known_user_ids()
        if uids:
            sample_uid = uids[0]
            print(f"\nUser sample: {sample_uid}")
            print("  Top genre:", engine.user_top_genre(sample_uid))
            print("  Recommendations:", engine.recommend_movies(sample_uid, 3))
    else:
        print("\n(No ratings loaded, skipping ranking checks.)")

    # --- Final summary printout ---
    print("\n--- Data Summary ---")
    print(engine.summary())


if __name__ == "__main__":
    movies_path, ratings_path = parse_args(sys.argv[1:])
    if not movies_path or not ratings_path:
        print("Usage:")
        print("  python test_movie_recommender.py --movies <path> --ratings <path>")
        sys.exit(1)

    run_test(movies_path, ratings_path)
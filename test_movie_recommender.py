#!/usr/bin/env python3
# test_movie_recommender.py
# Standard-library-only test harness for movie_recommender.Recommender

import os
import re
import sys
import glob
import math
import tempfile
from typing import Iterable, List, Tuple, Optional

# === Program Info / Import target class ===
try:
    from movie_recommender import Recommender
except Exception as e:
    print("❌ Could not import Recommender from movie_recommender.py")
    print(e)
    sys.exit(1)

LINE = "=" * 78


# === UTILS (must include) =====================================================

def expect(actual, expected, msg: str, tol: float = 1e-9):
    """
    Basic assertion helper:
    - If both are numbers, compare within tolerance.
    - If both are iterables of same length, compare elementwise (numbers by tol, else ==).
    - Else fallback to equality.
    """
    def _is_num(x):
        return isinstance(x, (int, float)) and not isinstance(x, bool)

    def _approx(a, b):
        if any(map(lambda v: isinstance(v, float) and (math.isnan(v) or math.isinf(v)), (a, b))):
            return a == b
        return abs(float(a) - float(b)) <= tol

    ok = True
    if _is_num(actual) and _is_num(expected):
        ok = _approx(actual, expected)
    elif isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)) and len(actual) == len(expected):
        for av, ev in zip(actual, expected):
            if _is_num(av) and _is_num(ev):
                if not _approx(av, ev):
                    ok = False
                    break
            else:
                if av != ev:
                    ok = False
                    break
    else:
        ok = (actual == expected)

    if not ok:
        raise AssertionError(f"{msg}\n  expected: {expected}\n  actual:   {actual}")


def assert_sorted_movies(rows: List[Tuple]):
    """
    Movies must be sorted by (avg desc, count desc, name asc, movie_id asc)
    Tuple shape: (movie_id, name_with_year, avg, count, genre)
    """
    def key(t):
        mid, name, avg, cnt, _genre = t
        # negatives for descending avg/count
        return (-float(avg), -int(cnt), str(name), str(mid))

    sorted_rows = sorted(rows, key=key)
    expect(rows, sorted_rows, "Movies not sorted by (avg desc, count desc, name asc, movie_id asc)")


def assert_sorted_genres(rows: List[Tuple]):
    """
    Genres must be sorted by (avg desc, count desc, genre asc)
    Tuple shape: (genre, genre_avg, contributing_movie_count)
    """
    def key(t):
        genre, gavg, gcount = t
        return (-float(gavg), -int(gcount), str(genre))

    sorted_rows = sorted(rows, key=key)
    expect(rows, sorted_rows, "Genres not sorted by (avg desc, count desc, genre asc)")


def verdict_from_summary(summary_text: str) -> Tuple[str, str]:
    """
    STRICT verdict for Phase B/C:
      - Find ALL counters whose KEY contains 'skipped' (case-insensitive), in 'key: number' or 'key=number' form.
      - If ANY such counter has value > 0 -> verdict = 'issues'.
      - ONLY when ALL '...skipped...' counters are exactly 0 -> verdict = 'valid'.
    Returns:
      (verdict, details)
      - verdict: 'valid' or 'issues'
      - details: for issues, a semicolon-joined 'key: val' list (e.g., 'movies_skipped_duplicate: 1; ratings_skipped_malformed: 2'),
                 empty string for valid.
    If no 'skipped' counters are present in the summary, we treat it as valid.
    """
    text = summary_text or ""
    matches = re.findall(r'([A-Za-z0-9_.-]*skipped[A-Za-z0-9_.-]*)\s*[:=]\s*(\d+)', text, flags=re.IGNORECASE)
    if not matches:
        return "valid", ""
    offenders = []
    for key, val in matches:
        try:
            n = int(val)
        except Exception:
            n = 0
        if n > 0:
            offenders.append(f"{key.strip()}: {n}")
    if offenders:
        return "issues", "; ".join(offenders)
    return "valid", ""


def _print_table(header: str, rows: Iterable[Tuple], max_rows: int = 10):
    print(header)
    c = 0
    for r in rows:
        print("  -", r)
        c += 1
        if c >= max_rows:
            break
    if c == 0:
        print("  (no rows)")
    print()


def _read_user_ratings_from_file(ratings_path: str) -> dict:
    """
    Returns {user_id: set(movie_name_with_year)} from ratings file.
    Format: movie_name_with_year|rating|user_id
    """
    data = {}
    if not os.path.isfile(ratings_path):
        return data
    with open(ratings_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) != 3:
                continue
            movie, rating, uid = parts
            data.setdefault(uid, set()).add(movie)
    return data


# === PHASE A – Primary feature tests ==========================================

def phase_a():
    print(LINE)
    print("PHASE A – Primary feature tests")
    print(LINE)

    movies_path = os.path.join("data", "movies.txt")
    ratings_path = os.path.join("data", "ratings.txt")

    if not os.path.isfile(movies_path) or not os.path.isfile(ratings_path):
        print("❌ Missing ./data/movies.txt or ./data/ratings.txt. Skipping Phase A.")
        print()
        return

    # Load data
    rec = Recommender()
    rec.reset_all()
    rec.load_movies(movies_path)
    rec.load_ratings(ratings_path)

    # Print summary
    try:
        summary_txt = rec.summary()
    except Exception:
        summary_txt = "(summary unavailable)"
    print(summary_txt)
    print()

    # Primary calls
    top_movies = rec.top_n_movies(10)
    _print_table("Top Movies (n=10):", top_movies, max_rows=10)
    assert_sorted_movies(top_movies)

    # Top in first available genre
    genres = list(rec.available_genres() or [])
    if genres:
        first_genre = sorted(genres)[0]
        top_in_genre = rec.top_n_movies_in_genre(first_genre, 10)
        _print_table(f"Top in Genre '{first_genre}' (n=10):", top_in_genre, max_rows=10)
        assert_sorted_movies(top_in_genre)
    else:
        first_genre = None
        print("No available genres reported.")
        print()

    # Top genres
    top_genres = rec.top_n_genres(10)
    _print_table("Top Genres (n=10):", top_genres, max_rows=10)
    assert_sorted_genres(top_genres)

    # Pick user with most ratings (parse ratings file)
    user_ratings = _read_user_ratings_from_file(ratings_path)
    if user_ratings:
        most_user = max(user_ratings.items(), key=lambda kv: len(kv[1]))[0]
        # user_top_genre (optional)
        try:
            utg = rec.user_top_genre(most_user)
        except Exception:
            utg = None
        print(f"user_top_genre({most_user}) -> {utg}")
        print()

        # Recommendations
        recs = rec.recommend_movies(most_user, k=3)
        _print_table(f"recommend_movies(user_id={most_user}, k=3):", recs, max_rows=3)
        # Assert recommendations don't include movies the user already rated
        already = user_ratings.get(most_user, set())
        rec_names = {row[1] for row in recs}  # name_with_year at index 1
        overlap = already.intersection(rec_names)
        expect(len(overlap), 0, f"Recommendations include already-rated titles for user {most_user}: {overlap}")
    else:
        print("No user ratings found in file; skipping user-focused assertions.")
        print()


# === PHASE B – Single-file validation =========================================

def phase_b():
    print(LINE)
    print("PHASE B – Single-file validation")
    print(LINE)

    data_dir = "data"
    if not os.path.isdir(data_dir):
        print("❌ Missing ./data directory. Skipping Phase B.")
        print()
        return

    # Determine reference movies file for ratings checks
    ref_movies = os.path.join(data_dir, "movies.txt")

    # Validate movies_*.txt
    movies_files = sorted(glob.glob(os.path.join(data_dir, "movies_*.txt")))
    if movies_files:
        print("Movies file verdicts:")
        for mp in movies_files:
            rec = Recommender()
            rec.reset_all()
            try:
                rec.load_movies(mp)
                summary_txt = rec.summary()
            except Exception as e:
                print(f"  {os.path.basename(mp)} -> ❌ issues (exception: {e})")
                continue
            verdict, details = verdict_from_summary(summary_txt)
            if verdict == "valid":
                print(f"  {os.path.basename(mp)} -> ✅ valid")
            else:
                # Explicitly list which counters triggered the wrong verdict
                print(f"  {os.path.basename(mp)} -> ❌ issues: issues: {details}")
        print()
    else:
        print("No movies_*.txt files found.")
        print()

    # Validate ratings_*.txt (with reference movies)
    ratings_files = sorted(glob.glob(os.path.join(data_dir, "ratings_*.txt")))
    if ratings_files:
        print("Ratings file verdicts (using reference movies file):")
        for rp in ratings_files:
            rec = Recommender()
            rec.reset_all()
            try:
                if os.path.isfile(ref_movies):
                    rec.load_movies(ref_movies)
                rec.load_ratings(rp)
                summary_txt = rec.summary()
            except Exception as e:
                print(f"  {os.path.basename(rp)} -> ❌ issues (exception: {e})")
                continue

            verdict, details = verdict_from_summary(summary_txt)
            if verdict == "valid":
                print(f"  {os.path.basename(rp)} -> ✅ valid")
            else:
                print(f"  {os.path.basename(rp)} -> ❌ issues: issues: {details}")
        


# === PHASE C – Synthetic edge suite ===========================================

def phase_c():
    print(LINE)
    print("PHASE C – Synthetic edge suite")
    print(LINE)

    # We'll craft small, in-memory datasets with both valid and erroneous lines.
    with tempfile.TemporaryDirectory() as tmpdir:
        m_clean = os.path.join(tmpdir, "m_clean.txt")
        r_clean = os.path.join(tmpdir, "r_clean.txt")
        m_bad_malformed = os.path.join(tmpdir, "m_bad_malformed.txt")
        r_bad_nonnum = os.path.join(tmpdir, "r_bad_nonnum.txt")
        r_bad_oor = os.path.join(tmpdir, "r_bad_oor.txt")
        r_bad_unknown = os.path.join(tmpdir, "r_bad_unknown.txt")
        r_bad_dupes = os.path.join(tmpdir, "r_bad_dupes.txt")

        # Movies format: genre|movie_id|movie_name_with_year
        movies_clean_lines = [
            "Comedy|1001|Groundhog Day (1993)",
            "Action|1002|Speed (1994)",
            "Drama|1003|The Shawshank Redemption (1994)",
            "Action|1004|Die Hard (1988)",
            "Sci-Fi|1005|The Matrix (1999)",
        ]
        with open(m_clean, "w", encoding="utf-8") as f:
            f.write("\n".join(movies_clean_lines))

        # Ratings format: movie_name_with_year|rating|user_id
        ratings_clean_lines = [
            "Groundhog Day (1993)|5|u1",
            "Groundhog Day (1993)|4.5|u2",
            "Speed (1994)|4.5|u1",
            "Speed (1994)|4.0|u3",
            "The Shawshank Redemption (1994)|4.0|u2",
            "Die Hard (1988)|3.0|u1",
            "The Matrix (1999)|4.0|u4",
        ]
        with open(r_clean, "w", encoding="utf-8") as f:
            f.write("\n".join(ratings_clean_lines))

        # Malformed movies: wrong column counts, empty lines
        with open(m_bad_malformed, "w", encoding="utf-8") as f:
            f.write("\n".join([
                "Comedy|1001",                          # missing name
                "NotAGenreOnly",                        # 1 column
                "|1002|Speed (1994)",                   # missing genre
                "Drama|1003|The Shawshank Redemption (1994)",
            ]))

        # Non-numeric rating
        with open(r_bad_nonnum, "w", encoding="utf-8") as f:
            f.write("\n".join([
                "Groundhog Day (1993)|N/A|u1",
                "Speed (1994)|4.0|u2",
            ]))

        # Out-of-range rating
        with open(r_bad_oor, "w", encoding="utf-8") as f:
            f.write("\n".join([
                "Groundhog Day (1993)|6.0|u1",   # likely out of 0-5
                "Speed (1994)|-1|u3",
            ]))

        # Unknown movie
        with open(r_bad_unknown, "w", encoding="utf-8") as f:
            f.write("\n".join([
                "Nonexistent Movie (1900)|4|u2",
                "Speed (1994)|4|u1",
            ]))

        # Duplicate ratings (same user and movie twice)
        with open(r_bad_dupes, "w", encoding="utf-8") as f:
            f.write("\n".join([
                "Speed (1994)|4|u1",
                "Speed (1994)|5|u1",
                "Groundhog Day (1993)|5|u1",
            ]))

        # === Run a clean case and assert Groundhog Day & Speed appear in top list
        rec = Recommender()
        rec.reset_all()
        rec.load_movies(m_clean)
        rec.load_ratings(r_clean)
        try:
            summary_txt = rec.summary()
        except Exception:
            summary_txt = "(summary unavailable)"
        print("Clean synthetic summary:\n", summary_txt, "\n", sep="")

        top_movies = rec.top_n_movies(10)
        names = [row[1] for row in top_movies]  # name_with_year
        expect(True, "Groundhog Day (1993)" in names, "Expected 'Groundhog Day (1993)' in top movies list")
        expect(True, "Speed (1994)" in names, "Expected 'Speed (1994)' in top movies list")
        assert_sorted_movies(top_movies)
        print("✅ Clean synthetic set produced expected top movies (and sorted correctly).")
        print()

        # === Erroneous cases: verify summary strictly by 'skipped' counters
        def run_err_case(label: str, movies_file: Optional[str], ratings_file: Optional[str]):
            rec = Recommender()
            rec.reset_all()
            if movies_file:
                rec.load_movies(movies_file)
            if ratings_file:
                # Always ensure movies are present; if not provided for the case, use clean movies
                if not movies_file:
                    rec.load_movies(m_clean)
                rec.load_ratings(ratings_file)
            try:
                s = rec.summary()
            except Exception as e:
                print(f"{label}: ❌ issues (exception: {e})")
                return
            verdict, details = verdict_from_summary(s)
            if verdict == "valid":
                print(f"{label}: ✅ valid")
            else:
                print(f"{label}: ❌ issues: wrong issues: {details}")

        run_err_case("Malformed movies rows", m_bad_malformed, r_clean)
        run_err_case("Non-numeric ratings", m_clean, r_bad_nonnum)
        run_err_case("Out-of-range ratings", m_clean, r_bad_oor)
        run_err_case("Unknown movies in ratings", m_clean, r_bad_unknown)
        run_err_case("Duplicate ratings by user/movie", m_clean, r_bad_dupes)
        print()


# === MAIN =====================================================================

def main():
    print(LINE)
    print("Running test_movie_recommender.py")
    print(LINE)
    print()

    # Phase A
    try:
        phase_a()
    except AssertionError as ae:
        print("❌ Phase A assertion failed:")
        print(ae)
        print()
    except Exception as e:
        print("❌ Phase A error:", e)
        print()

    # Phase B
    try:
        phase_b()
    except Exception as e:
        print("❌ Phase B error:", e)
        print()

    # Phase C
    try:
        phase_c()
    except AssertionError as ae:
        print("❌ Phase C assertion failed:")
        print(ae)
        print()
    except Exception as e:
        print("❌ Phase C error:", e)
        print()

    print(LINE)
    print("Done.")
    print(LINE)


if __name__ == "__main__":
    main()
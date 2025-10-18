"""
movie_recommender.py

A minimal, self-contained movie recommendation CLI using only Python's standard library.
Supports:
1. Load movies file
2. Load ratings file
3. Top N movies
4. Top N movies in a genre
5. Top N genres
6. User’s top genre
7. Recommend 3 movies for a user
8. Show data summary
9. Reset/clear all data
10. Exit

All parsing is robust:
- Skips malformed lines
- Skips unknown-movie ratings
- Skips non-numeric or out-of-range ratings [0,5]
- Keeps only the first rating a user gives a movie (later duplicates ignored)
- If movies are reloaded, ratings are cleared to avoid stale references

Tie-breaking rules:
- Movies: avg desc, count desc, name asc, movie_id asc
- Genres: avg desc, contributing_movie_count desc, genre asc

Case sensitivity:
- "movie_name_with_year" and "user_id" are case-sensitive (kept verbatim)
- Genre input in the CLI is case-insensitive, but original genre labels are preserved/displayed

Run:
    python movie_recommender.py
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import sys
import os


@dataclass(frozen=True)
class Movie:
    """Immutable record for a movie."""
    movie_id: int
    name_with_year: str
    genre: str


class Recommender:
    """
    Core in-memory engine for loading data and performing ranking/recommendation.

    Attributes
    ----------
    movies_by_id : Dict[int, Movie]
        Map of movie_id to Movie.
    movies_by_name : Dict[str, int]
        Map of exact movie_name_with_year (case-sensitive) to movie_id.
    genre_lookup : Dict[str, str]
        Map of lowercase genre to its original-cased label (first seen).
    ratings : Dict[Tuple[int, str], float]
        Map of (movie_id, user_id) -> rating (float in [0,5]).
    load_stats : Dict[str, int]
        Counters for summary/reporting across the last load operations.
    """

    def __init__(self) -> None:
        self.movies_by_id: Dict[int, Movie] = {}
        self.movies_by_name: Dict[str, int] = {}
        self.genre_lookup: Dict[str, str] = {}
        self.ratings: Dict[Tuple[int, str], float] = {}
        self.load_stats: Dict[str, int] = {}
        self._reset_stats()

    # ---------- Utilities ----------

    def _reset_stats(self) -> None:
        """Reset the summary counters used during (re)loads."""
        self.load_stats = {
            "movies_loaded": 0,
            "movies_skipped_malformed": 0,
            "movies_skipped_duplicate": 0,
            "ratings_loaded": 0,
            "ratings_skipped_malformed": 0,
            "ratings_skipped_unknown_movie": 0,
            "ratings_skipped_nonnumeric": 0,
            "ratings_skipped_out_of_range": 0,
            "ratings_skipped_duplicate_user_movie": 0,
            "ratings_skipped_empty": 0,
            "movies_skipped_empty": 0,
        }

    def reset_all(self) -> None:
        """Clear all in-memory data and counters."""
        self.movies_by_id.clear()
        self.movies_by_name.clear()
        self.genre_lookup.clear()
        self.ratings.clear()
        self._reset_stats()

    # ---------- Loading ----------

    def load_movies(self, path: str) -> None:
        """
        Load movies from file: "genre|movie_id|movie_name_with_year".
        - Skips malformed/empty lines.
        - Skips duplicates by movie_id or movie_name_with_year.
        - On reload, clears existing ratings to avoid stale references.
        """
        # Clear movies and ratings on reload
        self.movies_by_id.clear()
        self.movies_by_name.clear()
        self.genre_lookup.clear()
        self.ratings.clear()
        self._reset_stats()

        if not os.path.exists(path):
            print(f"Movies file not found: {path}")
            return
        

        try:
            with open(path, "r", encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line:
                        self.load_stats["movies_skipped_empty"] += 1
                        continue
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) != 3:
                        self.load_stats["movies_skipped_malformed"] += 1
                        continue

                    if not all(parts):
                        self.load_stats["movies_skipped_malformed"] += 1
                        continue

                    if len(line) > 2000:
                        self.load_stats["movies_skipped_malformed"] += 1
                        continue

                    genre, mid_str, name = parts
                    try:
                        mid = int(mid_str)
                    except ValueError:
                        self.load_stats["movies_skipped_malformed"] += 1
                        continue

                    # Duplicate checks
                    if mid in self.movies_by_id or name in self.movies_by_name:
                        self.load_stats["movies_skipped_duplicate"] += 1
                        continue

                    # Store
                    self.movies_by_id[mid] = Movie(mid, name, genre)
                    self.movies_by_name[name] = mid
                    lkey = genre.lower()
                    if lkey not in self.genre_lookup:
                        self.genre_lookup[lkey] = genre
                    self.load_stats["movies_loaded"] += 1
        except OSError as e:
            print(f"Error reading movies file: {e}")

        

    def load_ratings(self, path: str) -> None:
        """
        Load ratings from file: "movie_name_with_year|rating|user_id".
        - Skips malformed/empty lines.
        - Skips ratings for unknown movies.
        - Skips non-numeric ratings or ratings outside [0,5].
        - If a user rates the same movie multiple times, only the first is kept.
        """
        if not os.path.exists(path):
            print(f"Ratings file not found: {path}")
            return
        

        try:
            with open(path, "r", encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line:
                        self.load_stats["ratings_skipped_empty"] += 1
                        continue

                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) != 3:
                        self.load_stats["ratings_skipped_malformed"] += 1
                        continue

                    if not all(parts):
                        self.load_stats["ratings_skipped_malformed"] += 1
                        continue

                    if len(line) > 2000:
                        self.load_stats["ratings_skipped_malformed"] += 1
                        continue

                    name, rating_str, user_id = parts

                    # Unknown movies -> skip
                    mid = self.movies_by_name.get(name)
                    if mid is None:
                        self.load_stats["ratings_skipped_unknown_movie"] += 1
                        continue

                    # Rating numeric and in-range
                    try:
                        rating = float(rating_str)
                    except ValueError:
                        self.load_stats["ratings_skipped_nonnumeric"] += 1
                        continue
                    if not (0.0 <= rating <= 5.0):
                        self.load_stats["ratings_skipped_out_of_range"] += 1
                        continue

                    key = (mid, user_id)
                    if key in self.ratings:
                        self.load_stats["ratings_skipped_duplicate_user_movie"] += 1
                        continue

                    self.ratings[key] = rating
                    self.load_stats["ratings_loaded"] += 1
                    
        except OSError as e:
            print(f"Error reading ratings file: {e}")


    # ---------- Computation helpers ----------

    def _movie_aggregate(self) -> Dict[int, Tuple[float, int]]:
        """
        Compute sum and count for each movie_id based on current ratings.

        Returns
        -------
        Dict[int, Tuple[sum, count]]
        """
        agg: Dict[int, List[float]] = {}
        for (mid, _uid), r in self.ratings.items():
            agg.setdefault(mid, []).append(r)
        out: Dict[int, Tuple[float, int]] = {}
        for mid, lst in agg.items():
            out[mid] = (sum(lst), len(lst))
        return out

    def _movie_stats(self) -> Dict[int, Tuple[float, int]]:
        """
        Compute (average, count) for each movie_id with at least one rating.

        Returns
        -------
        Dict[int, Tuple[avg, count]]
        """
        sums_counts = self._movie_aggregate()
        stats: Dict[int, Tuple[float, int]] = {}
        for mid, (s, c) in sums_counts.items():
            if c > 0:
                stats[mid] = (s / c, c)
        return stats

    # ---------- Public feature functions ----------

    def top_n_movies(self, n: int) -> List[Tuple[int, str, float, int, str]]:
        """
        Rank all movies by average rating with tie-breaking.

        Parameters
        ----------
        n : int
            Number of movies to return.

        Returns
        -------
        List[Tuple[movie_id, name_with_year, avg, count, genre]]
        """
        stats = self._movie_stats()
        items: List[Tuple[int, str, float, int, str]] = []
        for mid, (avg, c) in stats.items():
            m = self.movies_by_id[mid]
            items.append((mid, m.name_with_year, avg, c, m.genre))

        items.sort(key=lambda x: (-x[2], -x[3], x[1], x[0]))
        return items[: max(0, n)]

    def top_n_movies_in_genre(self, genre_query: str, n: int) -> List[Tuple[int, str, float, int, str]]:
        """
        Rank movies within a given genre by average rating with tie-breaking.

        Parameters
        ----------
        genre_query : str
            Genre input (case-insensitive).
        n : int
            Number of movies to return.

        Returns
        -------
        List[Tuple[movie_id, name_with_year, avg, count, genre]]
        """
        if not self.genre_lookup:
            return []

        gkey = genre_query.lower()
        genre = self.genre_lookup.get(gkey)
        if genre is None:
            return []

        stats = self._movie_stats()
        items: List[Tuple[int, str, float, int, str]] = []
        for mid, (avg, c) in stats.items():
            m = self.movies_by_id[mid]
            if m.genre == genre:
                items.append((mid, m.name_with_year, avg, c, m.genre))

        items.sort(key=lambda x: (-x[2], -x[3], x[1], x[0]))
        return items[: max(0, n)]

    def top_n_genres(self, n: int) -> List[Tuple[str, float, int]]:
        """
        Rank genres by the average of per-movie averages, using only movies with ratings.

        Tie-breaking: avg desc, contributing_movie_count desc, genre asc.

        Returns
        -------
        List[Tuple[genre, genre_avg_of_avgs, contributing_movie_count]]
        """
        stats = self._movie_stats()
        per_genre: Dict[str, List[float]] = {}
        for mid, (avg, _c) in stats.items():
            g = self.movies_by_id[mid].genre
            per_genre.setdefault(g, []).append(avg)

        rows: List[Tuple[str, float, int]] = []
        for g, avgs in per_genre.items():
            if avgs:
                rows.append((g, sum(avgs) / len(avgs), len(avgs)))

        rows.sort(key=lambda x: (-x[1], -x[2], x[0]))
        return rows[: max(0, n)]

    def user_top_genre(self, user_id: str) -> Optional[Tuple[str, float, int]]:
        """
        Determine the user's most preferred genre:
        - For each genre, average ONLY this user's ratings on movies in that genre.
        - Tie-breaking: avg desc, count desc, genre asc.

        Parameters
        ----------
        user_id : str
            User identifier (kept case-sensitive).

        Returns
        -------
        Optional[Tuple[genre, avg, count]]
            None if user has no ratings.
        """
        # Collect user's ratings by genre
        by_genre: Dict[str, List[float]] = {}
        for (mid, uid), r in self.ratings.items():
            if uid == user_id:
                g = self.movies_by_id[mid].genre
                by_genre.setdefault(g, []).append(r)

        rows: List[Tuple[str, float, int]] = []
        for g, lst in by_genre.items():
            if lst:
                rows.append((g, sum(lst) / len(lst), len(lst)))

        if not rows:
            return None

        rows.sort(key=lambda x: (-x[1], -x[2], x[0]))
        return rows[0]

    def recommend_movies(self, user_id: str, k: int = 3) -> List[Tuple[int, str, float, int, str]]:
        """
        Recommend up to k movies for a user:
        1) Find user's top genre (via user_top_genre).
        2) Return the k most popular (overall) movies from that genre that the user has not rated.

        Parameters
        ----------
        user_id : str
            User identifier (case-sensitive).
        k : int
            Number of recommendations to return.

        Returns
        -------
        List[Tuple[movie_id, name_with_year, avg, count, genre]]
        """
        top = self.user_top_genre(user_id)
        if not top:
            return []

        genre = top[0]
        # Popular movies overall, filtered to genre
        popular_in_genre = self.top_n_movies_in_genre(genre, n=10_000)

        # Exclude movies the user already rated
        rated_mids = {mid for (mid, uid) in self.ratings.keys() if uid == user_id}
        recs = [row for row in popular_in_genre if row[0] not in rated_mids]
        return recs[: max(0, k)]

    def available_genres(self) -> list[str]:
        """
        Return all genres present in the currently loaded movies.
        Original-cased labels (as first seen in the movies file), sorted ascending.
        """
        # genre_lookup maps lowercase -> original label
        return sorted(self.genre_lookup.values())

    def known_user_ids(self) -> list[str]:
        """
        Return all distinct user_ids present in the currently loaded ratings.
        Sorted ascending (string compare).
        """
        uids = {uid for (_mid, uid) in self.ratings.keys()}
        return sorted(uids)

    # ---------- Summary ----------

    def summary(self) -> str:
        """
        Create a human-friendly summary of current data and last load stats.

        Returns
        -------
        str
            Summary describing totals and skipped counts.
        """
        movie_count = len(self.movies_by_id)
        rating_count = len(self.ratings)
        lines = [
            "=== Data Summary ===",
            f"Movies in memory: {movie_count}",
            f"Ratings in memory: {rating_count}",
            "",
            "=== Load Details (this session) ===",
        ]
        for k in sorted(self.load_stats.keys()):
            lines.append(f"{k}: {self.load_stats[k]}")
        return "\n".join(lines)


# ---------- CLI ----------

def _prompt_int(prompt: str) -> Optional[int]:
    """Prompt for an integer; return None if invalid."""
    try:
        val = int(input(prompt).strip())
        return val
    except ValueError:
        print("Please enter a valid integer.")
        return None


def _print_movies(rows: List[Tuple[int, str, float, int, str]]) -> None:
    """Pretty-print a list of movie rows."""
    if not rows:
        print("(no results)")
        return
    print(f"{'ID':>5}  {'AVG':>5}  {'CNT':>3}  {'GENRE':<15}  NAME")
    for mid, name, avg, cnt, genre in rows:
        print(f"{mid:>5}  {avg:>5.2f}  {cnt:>3}  {genre:<15}  {name}")


def _print_genres(rows: List[Tuple[str, float, int]]) -> None:
    """Pretty-print genre rankings."""
    if not rows:
        print("(no results)")
        return
    print(f"{'AVG':>5}  {'CNT':>3}  GENRE")
    for genre, avg, cnt in rows:
        print(f"{avg:>5.2f}  {cnt:>3}  {genre}")


def main() -> None:
    """Run the interactive command-line interface."""
    engine = Recommender()

    MENU = """
Movie Recommender
1. Load movies file
2. Load ratings file
3. Top N movies
4. Top N movies in a genre
5. Top N genres
6. User’s top genre
7. Recommend 3 movies for a user
8. Show data summary
9. Reset/clear all data
10. Exit
"""

    while True:
        print(MENU)
        choice = input("Choose an option (1-10): ").strip()

        if choice == "1":
            path = input("Path to movies file: ").strip()
            engine.load_movies(path)
            print("Movies loaded. (See 'Show data summary' for details.)")

        elif choice == "2":
            if not engine.movies_by_id:
                print("Load movies first.")
                continue
            path = input("Path to ratings file: ").strip()
            engine.load_ratings(path)
            print("Ratings loaded. (See 'Show data summary' for details.)")

        elif choice == "3":
            if not engine.ratings:
                print("No ratings available. Load ratings first.")
                continue
            n = _prompt_int("Top how many movies? ")
            if n is None or n <= 0:
                continue
            rows = engine.top_n_movies(n)
            _print_movies(rows)

        elif choice == "4":
            if not engine.ratings:
                print("No ratings available. Load ratings first.")
                continue
            if not engine.movies_by_id:
                print("Load movies first.")
                continue

            genres = engine.available_genres()
            if not genres:
                print("No genres available. Load movies first.")
                continue

            print("Available genres:")
            # simple comma-separated list to keep it compact
            print(", ".join(genres))

            genre_in = input("Genre: ").strip()
            n = _prompt_int("Top how many movies in this genre? ")
            if n is None or n <= 0:
                continue

            rows = engine.top_n_movies_in_genre(genre_in, n)
            if not rows:
                print("No results (unknown genre or no rated movies in that genre).")
            else:
                _print_movies(rows)

        elif choice == "5":
            if not engine.ratings:
                print("No ratings available. Load ratings first.")
                continue
            n = _prompt_int("Top how many genres? ")
            if n is None or n <= 0:
                continue
            rows = engine.top_n_genres(n)
            _print_genres(rows)

        elif choice == "6":
            if not engine.ratings:
                print("No ratings available. Load ratings first.")
                continue

            uids = engine.known_user_ids()
            if not uids:
                print("No user ratings found.")
                continue

            print("Known user IDs:")
            # show all; if your dataset is huge, you could truncate here
            print(", ".join(uids))

            uid = input("User ID: ").strip()
            res = engine.user_top_genre(uid)
            if not res:
                print("No ratings found for that user.")
            else:
                genre, avg, cnt = res
                print(f"Top genre for user '{uid}': {genre} (avg={avg:.2f}, count={cnt})")

        elif choice == "7":
            if not engine.ratings:
                print("No ratings available. Load ratings first.")
                continue
            uid = input("User ID (case-sensitive): ").strip()
            rows = engine.recommend_movies(uid, k=3)
            if not rows:
                print("No recommendations (user has no top genre or already rated all movies).")
            else:
                print("Recommendations:")
                _print_movies(rows)

        elif choice == "8":
            print(engine.summary())

        elif choice == "9":
            engine.reset_all()
            print("All data cleared.")

        elif choice == "10":
            print("Goodbye!")
            break

        else:
            print("Please choose a valid option (1-10).")


if __name__ == "__main__":
    main()

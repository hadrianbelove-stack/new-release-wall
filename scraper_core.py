import os, time, requests
from typing import Dict, Any, List, Optional

DEFAULT_SLEEP = 0.1
MAX_RETRIES = 3

class TMDB:
    def __init__(self, bearer: Optional[str] = None, timeout: float = 10.0):
        self.session = requests.Session()
        bearer = bearer or os.getenv("TMDB_BEARER")
        if not bearer:
            raise RuntimeError("TMDB_BEARER not set")
        self.session.headers.update({"Authorization": f"Bearer {bearer}"})
        self.timeout = timeout

    def _req(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        last_err = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                r = self.session.get(url, params=params or {}, timeout=self.timeout)
                if r.status_code in (429, 500, 502, 503, 504):
                    raise RuntimeError(f"tmdb {r.status_code}: {r.text[:200]}")
                r.raise_for_status()
                time.sleep(DEFAULT_SLEEP)
                return r.json()
            except Exception as e:
                last_err = e
                if attempt < MAX_RETRIES:
                    time.sleep(DEFAULT_SLEEP * attempt)
        raise RuntimeError(f"TMDB request failed after retries: {last_err}")

def get_release_types(tmdb: TMDB, movie_id: int, region: str) -> List[int]:
    data = tmdb._req(f"https://api.themoviedb.org/3/movie/{movie_id}/release_dates")
    types: List[int] = []
    for entry in data.get("results", []):
        if entry.get("iso_3166_1") == region.upper():
            for r in entry.get("release_dates", []):
                t = r.get("type")
                if isinstance(t, int):
                    types.append(t)
    return types

def get_providers(tmdb: TMDB, movie_id: int, region: str) -> Dict[str, List[Dict[str, Any]]]:
    data = tmdb._req(f"https://api.themoviedb.org/3/movie/{movie_id}/watch/providers")
    region_block = (data.get("results") or {}).get(region.upper()) or {}
    return {
        "rent": region_block.get("rent") or [],
        "buy": region_block.get("buy") or [],
        "stream": region_block.get("flatrate") or [],
    }

def get_details(tmdb: TMDB, movie_id: int) -> Dict[str, Any]:
    return tmdb._req(f"https://api.themoviedb.org/3/movie/{movie_id}")

def get_credits(tmdb: TMDB, movie_id: int) -> Dict[str, Any]:
    return tmdb._req(f"https://api.themoviedb.org/3/movie/{movie_id}/credits")

def normalize_record(
    movie: Dict[str, Any],
    providers: Dict[str, List[Dict[str, Any]]],
    release_types: List[int],
    details: Dict[str, Any],
    credits: Dict[str, Any],
) -> Dict[str, Any]:
    year = None
    try:
        if movie.get("release_date"):
            year = int((movie["release_date"] or "")[:4])
    except Exception:
        year = None
    directors = [p["name"] for p in credits.get("crew", []) if p.get("job") == "Director"][:2]
    cast = [p["name"] for p in credits.get("cast", [])][:2]
    return {
        "id": movie.get("id"),
        "title": movie.get("title") or movie.get("name"),
        "year": year,
        "providers": providers,
        "has_digital": (4 in release_types) or (6 in release_types) or any(providers.get(k) for k in ("rent","buy","stream")),
        "release_types": release_types,
        "theatrical_date": None,
        "digital_date": None,
        "credits": {"director": directors, "cast": cast},
        "runtime": details.get("runtime"),
        "studio": (details.get("production_companies") or [{}])[0].get("name") if details.get("production_companies") else None,
        "overview": details.get("overview"),
        "poster_url": f"https://image.tmdb.org/t/p/w500{movie.get('poster_path')}" if movie.get("poster_path") else None,
    }
# adapter.py
from datetime import datetime

# Map store names to short platform codes the UI shows
PLATFORM_MAP = {
    "Apple TV": "itunes",
    "iTunes": "itunes",
    "Amazon Prime Video": "amazon",
    "Amazon": "amazon",
    "Netflix": "other",
    "YouTube": "youtube",
    "Google Play Movies": "google",
    "Vudu": "vudu",
    "Max": "other",
    "Hulu": "other",
    "Disney Plus": "other",
    "MUBI": "mubi",
    "Criterion Channel": "other",
}

def to_iso(d):
    # Accepts: datetime, 'YYYY-MM-DD', or already ISO; returns ISO string
    if isinstance(d, datetime):
        return d.isoformat()
    if isinstance(d, str):
        try:
            return datetime.fromisoformat(d).isoformat()
        except Exception:
            try:
                return datetime.strptime(d, "%Y-%m-%d").isoformat()
            except Exception:
                return datetime.utcnow().isoformat()
    return datetime.utcnow().isoformat()

def platform_entry(store_name, url=None, rent=None, buy=None):
    p = PLATFORM_MAP.get(store_name, "other")
    entry = {"platform": p, "url": url or ""}
    if rent is not None:
        entry["rent"] = {"price": float(rent)}  # price as number
    if buy is not None:
        entry["buy"] = {"price": float(buy)}
    return entry

def normalize_title(item):
    """
    Convert ONE scraped item into the UI schema.

    Expected incoming keys (examples):
      item["title"], item["year"], item["genres"] (list or comma string),
      item["availability_date"] (home-viewing date),
      item["stores"] -> list of dicts like:
         {"name": "Apple TV", "url": "...", "rent": 5.99, "buy": 14.99}
      item["id"] or any unique key (fallback: title+year)
      item["poster"] (optional)
    """
    title = item.get("title", "").strip()
    year = item.get("year")
    genres = item.get("genres") or []
    if isinstance(genres, str):
        genres = [g.strip() for g in genres.split(",") if g.strip()]
    availability = to_iso(item.get("availability_date") or item.get("date") or "")
    poster = item.get("poster_url") or item.get("poster") or ""

    stores = item.get("stores") or []
    platforms = []
    for s in stores:
        platforms.append(
            platform_entry(
                store_name=s.get("name", ""),
                url=s.get("url") or "",
                rent=s.get("rent"),
                buy=s.get("buy"),
            )
        )

    # Ensure a stable id
    uid = item.get("id") or f"{title.lower()}:{year or ''}"

    return {
        "id": uid,
        "title": title,
        "poster": poster,
        "year": year if isinstance(year, int) else (int(year) if str(year).isdigit() else None),
        "genres": genres,
        "availabilityDate": availability,
        "platforms": platforms,
    }

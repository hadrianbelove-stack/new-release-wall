#!/usr/bin/env python3
import argparse, os, sys, json, datetime, time
from typing import Optional
import requests, yaml
from urllib.parse import quote_plus
from jinja2 import Template

# --- Optional normalizer: if adapter.py isn't present, use a no-op ---
try:
    from adapter import normalize_title  # type: ignore
except Exception:
    def normalize_title(rec):  # fallback
        return rec

# Optional TMDB v4 bearer for poster fallback (ok if absent)
TMDB_BEARER = os.getenv("TMDB_BEARER")

# ---------- Simple, resilient HTTP helper ----------
def safe_json_get(url, params=None, timeout=10, retries=3, headers=None):
    for i in range(retries):
        try:
            r = requests.get(url, params=params or {}, headers=headers or {}, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(1.5 * (i + 1))

# ---------- Config ----------
def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

# ---------- TMDB / OMDb ----------
def tmdb_get(path, params, api_key):
    url = f"https://api.themoviedb.org/3{path}"
    params = dict(params or {})
    params["api_key"] = api_key
    return safe_json_get(url, params=params, timeout=10, retries=3)

def omdb_rt_score(title, year, omdb_api_key, imdb_id=None):
    if not omdb_api_key:
        return None
    try:
        q = {"apikey": omdb_api_key, "tomatoes": "true", "type": "movie"}
        if imdb_id:
            q["i"] = imdb_id
        else:
            q["t"] = title
            if year:
                q["y"] = year
        data = safe_json_get("https://www.omdbapi.com/", params=q, timeout=8, retries=3)
        if data.get("Response") != "True":
            return None
        for rsrc in data.get("Ratings", []) or []:
            if rsrc.get("Source") == "Rotten Tomatoes":
                val = (rsrc.get("Value") or "").strip().rstrip("%")
                return int(val) if val.isdigit() else None
        return None
    except Exception:
        return None

def fetch_poster(title: str, year: Optional[int]):
    """
    Optional fallback: search TMDB for a poster via v4 bearer.
    Returns None if TMDB_BEARER is not set or nothing found.
    """
    if not TMDB_BEARER:
        return None
    headers = {"Authorization": f"Bearer {TMDB_BEARER}"}
    params = {"query": title}
    if year:
        params["year"] = year
    try:
        data = safe_json_get("https://api.themoviedb.org/3/search/movie",
                             params=params, headers=headers, timeout=10, retries=3)
        results = data.get("results", []) or []
        if results:
            poster_path = results[0].get("poster_path")
            if poster_path:
                return f"https://image.tmdb.org/t/p/w500{poster_path}"
    except Exception:
        pass
    return None

def get_provider_map(region, api_key):
    data = tmdb_get("/watch/providers/movie", {"watch_region": region}, api_key)
    name_to_id, id_to_name = {}, {}
    for p in data.get("results", []) or []:
        pid = p.get("provider_id")
        pname = p.get("provider_name")
        if pid and pname:
            name_to_id[pname.lower()] = pid
            id_to_name[pid] = pname
    return name_to_id, id_to_name

def normalize_store_names(store_csv, name_to_id):
    wanted = []
    if not store_csv:
        return wanted
    for raw in [s.strip() for s in store_csv.split(",") if s.strip()]:
        key = raw.lower()
        if key in name_to_id:
            wanted.append(name_to_id[key]); continue
        # contains
        found = None
        for n, pid in name_to_id.items():
            if key in n:
                found = pid; break
        if found:
            wanted.append(found); continue
        # startswith
        for n, pid in name_to_id.items():
            if n.startswith(key):
                found = pid; break
        if found:
            wanted.append(found); continue
        print(f"[warn] Could not match store '{raw}' to any TMDB provider")
    return sorted(list(set(wanted)))

# ---------- Discovery (broad fetch, no provider pre-filter) ----------
def discover_movies(region, start_date, end_date, provider_ids, api_key, max_pages=0):
    results = []
    page = 1
    while True:
        print(f"Fetching page {page}...", flush=True)
        params = {
            "sort_by": "primary_release_date.desc",
            "region": region,
            "watch_region": region,
            "include_adult": "false",
            "include_video": "false",
            "with_release_type": "3|4|5|6",  # theatrical/digital/TV (wide)
            "release_date.gte": start_date,
            "with_watch_monetization_types": "flatrate|ads|rent|buy|free",
            "release_date.lte": end_date,
            "page": page,
        }
        data = tmdb_get("/discover/movie", params, api_key)
        page_items = data.get("results", []) or []
        results.extend(page_items)

        if not page_items:
            break
        total_pages = int(data.get("total_pages", page))
        if page >= total_pages:
            break
        if max_pages and page >= max_pages:
            break
        page += 1
    return results

def get_us_digital_date(tmdb_id, api_key, region):
    # Region-specific digital/TV release dates (4 = Digital, 6 = TV)
    data = tmdb_get(f"/movie/{tmdb_id}/release_dates", {}, api_key)
    for rec in data.get("results", []) or []:
        if rec.get("iso_3166_1") != region:
            continue
        dates = rec.get("release_dates", []) or []
        candidates = [d.get("release_date") for d in dates if d.get("type") in (4, 6)]
        candidates = [c for c in candidates if c]
        if candidates:
            return min(candidates)[:10]  # earliest digital/TV date, YYYY-MM-DD
    return None

def tmdb_imdb_id(tmdb_id, api_key):
    data = tmdb_get(f"/movie/{tmdb_id}/external_ids", {}, api_key)
    return data.get("imdb_id")

def tmdb_trailer_url(tmdb_id, api_key):
    data = tmdb_get(f"/movie/{tmdb_id}/videos",
                    {"include_video_language": "en,null"}, api_key)
    vids = data.get("results", []) or []
    best = None
    for v in vids:
        if v.get("site") == "YouTube" and v.get("type") == "Trailer":
            if v.get("official"):
                best = v; break
            if not best:
                best = v
    if best and best.get("key"):
        return f"https://www.youtube.com/watch?v={best['key']}"
    return None

def movie_watch_providers(tmdb_id, region, api_key):
    data = tmdb_get(f"/movie/{tmdb_id}/watch/providers", {}, api_key)
    loc = data.get("results", {}).get(region, {})
    providers = set()
    for cat in ["flatrate", "rent", "buy", "ads", "free"]:
        for p in loc.get(cat, []) or []:
            pname = p.get("provider_name")
            if pname:
                providers.add(pname)
    tmdb_watch_link = loc.get("link") or f"https://www.themoviedb.org/movie/{tmdb_id}/watch"
    return sorted(list(providers)), tmdb_watch_link

# ---------- Output ----------
def render_markdown(items, site_title, window_label, region, store_names):
    lines = [f"# {site_title}", "", f"_Window: {window_label} • Region: {region} • Stores: {', '.join(store_names) if store_names else 'Any'}_", ""]
    for it in items:
        providers = ", ".join(it["providers"]) if it["providers"] else "—"
        rt = f'{it["rt_score"]}%' if it["rt_score"] is not None else "—"
        tm = f'{it.get("tmdb_vote","—")}'
        lines.append(
            f"- **{it['title']}** ({it.get('year','—')}) — RT: {rt} • TMDB: {tm} • Providers: {providers} — "
            f"[Watch options]({it['tmdb_watch_link']}) | [JustWatch]({it['justwatch_search_link']}) | [TMDB]({it['tmdb_url']})"
        )
    return "\n".join(lines) + "\n"

def render_site(items, site_title, window_label, region, store_names):
    tpl_path = os.path.join("templates", "site.html")
    with open(tpl_path, "r", encoding="utf-8") as f:
        tpl = Template(f.read())
    html = tpl.render(
        site_title=site_title,
        window_label=window_label,
        region=region,
        store_names=store_names,
        items=items,
        generated_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    )
    out_dir = os.path.join("output", "site")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

def within_date_window(days, start, end):
    if days is not None:
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=days)
        return start_date.isoformat(), end_date.isoformat(), f"Last {days} days"
    if start and end:
        return start, end, f"{start} → {end}"
    raise SystemExit("Provide either --days or both --start and --end")

# ---------- Main ----------
def main():
    parser = argparse.ArgumentParser(description="Generate 'The New Release Wall' list and site.")
    parser.add_argument("--region", default="US", help="Country/region code (e.g., US)")
    parser.add_argument("--days", type=int, default=None, help="Use rolling window of last N days")
    parser.add_argument("--start", type=str, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, help="End date YYYY-MM-DD")
    parser.add_argument("--stores", type=str, default="Netflix,Amazon Prime Video,Apple TV,YouTube", help="Comma-separated store names to include")
    parser.add_argument("--max-pages", type=int, default=0, help="Max TMDB pages to search (0 = all)")
    parser.add_argument("--digital", action="store_true", help="Filter by region-specific DIGITAL/TV date (type 4/6)")
    parser.add_argument("--only-current-year", action="store_true", help="Exclude reissues; keep only titles whose original release year is the current year.")
    args = parser.parse_args()

    cfg = load_config()
    tmdb_key = cfg.get("tmdb_api_key", "")
    omdb_key = cfg.get("omdb_api_key", "")
    min_rt = int(cfg.get("min_rotten_tomatoes", 1))
    site_title = cfg.get("site_title", "The New Release Wall")

    # window
    start_date, end_date, window_label = within_date_window(args.days, args.start, args.end)

    # providers
    name_to_id, id_to_name = get_provider_map(args.region, tmdb_key)
    provider_ids = normalize_store_names(args.stores, name_to_id)
    store_names = [id_to_name[pid] for pid in provider_ids] if provider_ids else []

    # fetch
    movies = discover_movies(args.region, start_date, end_date, provider_ids, tmdb_key, args.max_pages)
    print(f"DEBUG discover: {len(movies)}", flush=True)

    # dedupe by (title_lower, year)
    seen, cleaned = set(), []
    for m in movies:
        title = (m.get("title") or m.get("original_title") or "").strip()
        year = (m.get("release_date") or "0000-00-00")[:4]
        key = (title.lower(), year)
        if key in seen:
            continue
        seen.add(key)
        cleaned.

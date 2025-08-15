# The New Release Wall

A small, no-code-friendly script that compiles **new movie releases** available for **selected streaming stores** (Netflix, Amazon Prime Video, Apple iTunes/TV, YouTube, etc.), filters by **Rotten Tomatoes score ≥ 1%** (via OMDb), deduplicates across stores, and exports:

- `output/list.md` — Substack-ready Markdown (with hyperlinks)
- `output/site/` — a clean static website you can host anywhere

## What you need
- **TMDB API key** (free): https://www.themoviedb.org/settings/api — create a (free) account, then request a key.
- **OMDb API key** (cheap/patreon): https://www.omdbapi.com/apikey.aspx — needed to fetch Rotten Tomatoes ratings.

> Why TMDB? It has a clean **Discover** endpoint with watch-provider filters and a **watch/providers** API that maps availability per country. We use OMDb to fetch **Rotten Tomatoes** % when available.

## Quick Start

1) Install Python 3.10+
2) In Terminal:
```bash
cd new-release-wall
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
3) Copy `config.example.yaml` → `config.yaml` and fill your keys.
4) Run examples:

**Weekly wall (last 7 days):**
```bash
python new_release_wall.py --region US --days 7 --stores "Netflix,Amazon Prime Video,Apple iTunes,YouTube"
```

**Specific date range:**
```bash
python new_release_wall.py --region US --start 2025-08-01 --end 2025-08-10 --stores "Netflix,Amazon Prime Video,Apple iTunes,YouTube"
```

Outputs:
- `output/list.md` — paste into Substack as Markdown (or use HTML file)
- `output/site/index.html` — your simple, linkable website (**The New Release Wall**)

## Notes & Roadmap
- **Shop links**: We link to TMDB’s *Watch* page and a direct **JustWatch search** for each title. This reliably routes users to the right store for their region. We can add deeper store-specific links later (Apple iTunes via iTunes Search API, etc.).
- **Country/Region**: Defaults to `US`. Change `--region` as needed.
- **Extending stores**: Pass any set of store names found by TMDB (the script will auto-match provider names).


Last updated: Thu Aug 14 17:13:53 PDT 2025

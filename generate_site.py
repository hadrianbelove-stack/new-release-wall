#!/usr/bin/env python3
"""
Site generator using new VHS-style template
"""
import json
import os
import requests
import time
from datetime import datetime
from jinja2 import FileSystemLoader, Environment, Template
from collections import defaultdict

def month_name_filter(month_str):
    """Convert month number to name"""
    months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    try:
        return months[int(month_str)]
    except:
        return 'Unknown'

def create_justwatch_url(title):
    """Create direct JustWatch URL from movie title with fallback to search"""
    if not title:
        return "https://www.justwatch.com/us"
    
    # Special cases for known movie URL patterns
    special_cases = {
        'Deadpool & Wolverine': 'deadpool-3',
        'Deadpool 3': 'deadpool-3',
        'Inside Out 2': 'inside-out-2',
        'A Quiet Place: Day One': 'a-quiet-place-day-one',
        'Beetlejuice Beetlejuice': 'beetlejuice-2',
        'The Bad Guys 2': 'the-bad-guys-2',
        'Mission: Impossible - The Final Reckoning': 'mission-impossible-8',
        'Mission Impossible - The Final Reckoning': 'mission-impossible-8',
        'Mission: Impossible 8': 'mission-impossible-8',
    }
    
    if title in special_cases:
        return f"https://www.justwatch.com/us/movie/{special_cases[title]}"
    
    # Convert title to JustWatch URL slug
    slug = title.lower()
    
    # Remove common articles from beginning only
    articles = ['the ', 'a ', 'an ']
    for article in articles:
        if slug.startswith(article):
            slug = slug[len(article):]
    
    # Replace special characters and spaces
    slug = slug.replace('&', 'and')
    slug = slug.replace("'", '')
    slug = slug.replace('"', '')
    slug = slug.replace(':', '')
    slug = slug.replace('.', '')
    slug = slug.replace(',', '')
    slug = slug.replace('!', '')
    slug = slug.replace('?', '')
    slug = slug.replace('(', '')
    slug = slug.replace(')', '')
    slug = slug.replace('[', '')
    slug = slug.replace(']', '')
    slug = slug.replace('/', '')
    slug = slug.replace('\\', '')
    slug = slug.replace('#', '')
    
    # Replace spaces and multiple dashes with single dash
    slug = '-'.join(slug.split())
    slug = '-'.join(filter(None, slug.split('-')))  # Remove empty parts
    
    # If slug is too short or empty, fallback to search
    if len(slug) < 2:
        title_encoded = title.replace(' ', '+').replace('&', '%26')
        return f"https://www.justwatch.com/us/search?q={title_encoded}"
    
    return f"https://www.justwatch.com/us/movie/{slug}"

def get_tmdb_api_key():
    """Get TMDB API key from config"""
    try:
        with open('config.yaml', 'r') as f:
            import yaml
            config = yaml.safe_load(f)
            return config.get('tmdb_api_key')
    except:
        return None

def get_rt_score_direct(title, year):
    """Get RT score by scraping Rotten Tomatoes directly"""
    try:
        import urllib.parse
        # Create search URL for RT
        search_query = f"{title} {year}" if year else title
        search_url = f"https://www.rottentomatoes.com/search?search={urllib.parse.quote(search_query)}"
        
        # Use WebFetch to get RT page and extract score
        from tools import WebFetch  # This won't work in current context
        # For now, return None and we'll use a different approach
        return None
    except Exception as e:
        print(f"Error getting direct RT score for {title}: {e}")
    return None

def get_tmdb_movie_details(tmdb_id):
    """Get comprehensive movie details from TMDB"""
    api_key = get_tmdb_api_key()
    if not api_key:
        return {
            'poster_url': 'https://via.placeholder.com/160x240',
            'director': 'Director N/A',
            'cast': [],
            'synopsis': 'Synopsis not available.',
            'runtime': None,
            'studio': 'Studio N/A',
            'rating': 'NR',
            'trailer_url': None,
            'rt_url': None
        }
    
    # Get basic movie details
    movie_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}"
    credits_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/credits"
    videos_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/videos"
    
    try:
        # Fetch movie details
        movie_response = requests.get(movie_url, params={'api_key': api_key})
        credits_response = requests.get(credits_url, params={'api_key': api_key})
        videos_response = requests.get(videos_url, params={'api_key': api_key})
        
        result = {
            'poster_url': 'https://via.placeholder.com/160x240',
            'director': 'Director N/A',
            'cast': [],
            'synopsis': 'Synopsis not available.',
            'runtime': None,
            'studio': 'Studio N/A',
            'rating': 'NR',
            'trailer_url': None,
            'rt_url': None
        }
        
        if movie_response.status_code == 200:
            movie_data = movie_response.json()
            
            # Poster
            poster_path = movie_data.get('poster_path')
            if poster_path:
                result['poster_url'] = f"https://image.tmdb.org/t/p/w500{poster_path}"
            
            # Synopsis
            result['synopsis'] = movie_data.get('overview', 'Synopsis not available.')
            
            # Runtime
            runtime = movie_data.get('runtime')
            result['runtime'] = runtime if runtime else None
            
            # Studio
            production_companies = movie_data.get('production_companies', [])
            if production_companies:
                result['studio'] = production_companies[0].get('name', 'Studio N/A')
            
            # Try to create RT URL using IMDB ID
            imdb_id = movie_data.get('imdb_id')
            if imdb_id:
                result['rt_url'] = f"https://www.rottentomatoes.com/m/{imdb_id}"
        
        if credits_response.status_code == 200:
            credits_data = credits_response.json()
            
            # Director
            for crew in credits_data.get('crew', []):
                if crew.get('job') == 'Director':
                    result['director'] = crew.get('name', 'Director N/A')
                    break
            
            # Cast (first 3)
            cast_list = []
            for actor in credits_data.get('cast', [])[:3]:
                name = actor.get('name')
                if name:
                    cast_list.append(name)
            result['cast'] = cast_list
        
        if videos_response.status_code == 200:
            videos_data = videos_response.json()
            
            # Find official trailer
            for video in videos_data.get('results', []):
                if (video.get('type') == 'Trailer' and 
                    video.get('site') == 'YouTube' and 
                    video.get('official', False)):
                    result['trailer_url'] = f"https://www.youtube.com/watch?v={video['key']}"
                    break
            
            # If no official trailer, take the first trailer
            if not result['trailer_url']:
                for video in videos_data.get('results', []):
                    if video.get('type') == 'Trailer' and video.get('site') == 'YouTube':
                        result['trailer_url'] = f"https://www.youtube.com/watch?v={video['key']}"
                        break
        
        return result
        
    except Exception:
        return {
            'poster_url': 'https://via.placeholder.com/160x240',
            'director': 'Director N/A',
            'cast': [],
            'synopsis': 'Synopsis not available.',
            'runtime': None,
            'studio': 'Studio N/A',
            'rating': 'NR',
            'trailer_url': None,
            'rt_url': None
        }

def render_site_enhanced(items, site_title, window_label, region, store_names):
    """Render site with flip cards and date dividers."""
    
    # Group movies by date
    movies_by_date = defaultdict(list)
    for item in items:
        date = item.get('digital_date', '')[:10]
        if date:
            movies_by_date[date].append(item)
    
    # Sort dates descending (newest first)
    sorted_dates = sorted(movies_by_date.keys(), reverse=True)
    
    # Prepare data for template
    template_data = []
    for date_str in sorted_dates:
        # Parse date for display
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        date_info = {
            'month_short': date_obj.strftime('%b').upper(),
            'day': date_obj.strftime('%d').lstrip('0'),
            'year': date_obj.strftime('%Y')
        }
        template_data.append((date_info, movies_by_date[date_str]))
    
    # Load and render template
    tpl_path = os.path.join("templates", "site_enhanced.html")
    with open(tpl_path, "r", encoding="utf-8") as f:
        tpl = Template(f.read())
    
    html = tpl.render(
        site_title=site_title,
        window_label=window_label,
        region=region,
        store_names=store_names,
        movies_by_date=template_data,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M")
    )
    
    # Write output
    out_dir = os.path.join("output", "site")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

def generate_site():
    """Generate the VHS-style website"""
    
    # Load movie data
    with open('output/data.json', 'r') as f:
        movies = json.load(f)
    
    print(f"Loaded {len(movies)} movies")
    
    # Transform tracking data for new template
    items = []
    for movie in movies:
        # Extract year from digital_date if available
        year = '2025'
        if movie.get('digital_date'):
            year = movie['digital_date'][:4]
        elif movie.get('theatrical_date'):
            year = movie['theatrical_date'][:4]
        
        # Get comprehensive movie details from TMDB
        tmdb_details = get_tmdb_movie_details(movie.get('tmdb_id')) if movie.get('tmdb_id') else {}
        
        # Get direct trailer URL from TMDB API
        trailer_url = tmdb_details.get('trailer_url') if tmdb_details else None
        if not trailer_url and movie.get('tmdb_id'):
            # Fallback to search if no direct trailer found
            trailer_url = f"https://www.youtube.com/results?search_query={movie.get('title', '')}+{year}+trailer"
        
        # Create direct JustWatch link
        watch_link = create_justwatch_url(movie.get('title', ''))
        
        # Only show watch link if there are actual providers
        providers = movie.get('providers', {})
        has_providers = bool(providers.get('rent') or providers.get('buy') or providers.get('stream'))
        if not has_providers:
            watch_link = '#'
        
        # Combine all providers for display
        all_providers = []
        if providers.get('stream'):
            all_providers.extend(providers['stream'])
        if providers.get('rent'):
            all_providers.extend(providers['rent'])
        if providers.get('buy'):
            all_providers.extend(providers['buy'])
        
        # Try to get RT score from multiple sources
        rt_score = None
        if movie.get('rt_score'):
            rt_score = movie['rt_score']
        elif movie.get('review_data') and isinstance(movie['review_data'], dict):
            rt_score = movie['review_data'].get('rt_score')
        # else:
        #     # Fetch RT score directly if not in database (disabled for now)
        #     try:
        #         from rt_score_fetcher import get_rt_score_with_fallbacks
        #         rt_score = get_rt_score_with_fallbacks(movie.get('title', ''), year)
        #         if rt_score:
        #             print(f"  🍅 Fetched RT score for {movie.get('title', '')}: {rt_score}%")
        #         time.sleep(0.5)  # Rate limiting
        #     except Exception as e:
        #         print(f"  ❌ Failed to fetch RT score for {movie.get('title', '')}: {e}")
        #         rt_score = None
        
        item = {
            'title': movie.get('title', 'Unknown'),
            'year': year,
            'poster_url': tmdb_details.get('poster_url', 'https://via.placeholder.com/160x240'),
            'director': tmdb_details.get('director', 'Director N/A'),
            'cast': tmdb_details.get('cast', []),
            'synopsis': tmdb_details.get('synopsis', 'Synopsis not available.'),
            'digital_date': movie.get('digital_date', '').split('T')[0] if movie.get('digital_date') else '',
            'trailer_url': trailer_url,
            'rt_url': tmdb_details.get('rt_url'),
            'watch_link': watch_link,
            'rt_score': rt_score,
            'runtime': tmdb_details.get('runtime'),
            'studio': tmdb_details.get('studio', 'Studio N/A'),
            'rating': tmdb_details.get('rating', 'NR'),
            'providers': all_providers[:3]  # Show first 3 platforms
        }
        items.append(item)
    
    # Sort by digital date
    items.sort(key=lambda x: x['digital_date'] if x['digital_date'] else '9999-12-31')
    
    # Use enhanced rendering with flip cards and date dividers
    render_site_enhanced(
        items=items,
        site_title="New Release Wall",
        window_label="Digital Releases",
        region="US",
        store_names=["iTunes", "Vudu", "Amazon", "Google Play"]
    )
    
    print("✓ Generated output/site/index.html with enhanced flip cards and date dividers")

if __name__ == '__main__':
    generate_site()
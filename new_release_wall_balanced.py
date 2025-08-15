import argparse, os, sys, json, time
from datetime import datetime, timedelta
import requests, yaml
from jinja2 import Template

def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

def check_has_reviews(title, year, config):
    """Quick check if movie has any critical reviews via OMDb"""
    try:
        params = {
            'apikey': config['omdb_api_key'],
            't': title,
        }
        if year:
            params['y'] = str(year)
            
        response = requests.get('http://www.omdbapi.com/', params=params)
        data = response.json()
        
        if data.get('Response') == 'True':
            review_info = {}
            
            # Check for any review data (more lenient than smart version)
            if data.get('Metascore', 'N/A') != 'N/A':
                review_info['metacritic'] = data['Metascore']
            
            for rating in data.get('Ratings', []):
                if rating['Source'] == 'Rotten Tomatoes':
                    review_info['rt_score'] = rating['Value'].rstrip('%')
            
            # More lenient IMDB threshold (10+ votes instead of 50+)
            votes_str = data.get('imdbVotes', '0').replace(',', '').replace('N/A', '0')
            if votes_str and votes_str != '0':
                votes = int(votes_str)
                if votes > 10:  # Lowered from 50 to 10
                    review_info['imdb_votes'] = votes
                    review_info['imdb_rating'] = data.get('imdbRating', 'N/A')
            
            return bool(review_info), review_info
                
        return False, None
    except Exception as e:
        return False, None

def get_balanced_releases(region="US", days=14, max_pages=5):
    """Get releases with balanced filtering - less restrictive than smart version"""
    config = load_config()
    api_key = config['tmdb_api_key']
    
    today = datetime.now()
    start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")
    
    print(f"Fetching releases from {start_date} to {end_date}...")
    
    all_movies = []
    
    for page in range(1, max_pages + 1):
        print(f"Fetching page {page}...")
        
        params = {
            'api_key': api_key,
            'region': region,
            'with_release_type': '4|6',  # Digital and TV
            'primary_release_date.gte': start_date,
            'primary_release_date.lte': end_date,
            'sort_by': 'release_date.desc',
            'page': page
        }
        
        response = requests.get('https://api.themoviedb.org/3/discover/movie', params=params)
        movies = response.json().get('results', [])
        
        if not movies:
            break
            
        all_movies.extend(movies)
        time.sleep(0.3)
    
    print(f"\nFound {len(all_movies)} total movies. Applying balanced filtering...")
    
    curated = []
    included_count = 0
    
    for movie in all_movies:
        title = movie.get('title', '')
        year = movie.get('release_date', '')[:4] if movie.get('release_date') else None
        
        include = False
        reason = ""
        review_data = {}
        
        # Tier 1: Auto-include popular movies (lowered thresholds)
        if movie.get('vote_count', 0) >= 20:  # Lowered from 50 to 20
            include = True
            reason = f"TMDB popular ({movie['vote_count']} votes)"
        
        # Tier 2: Auto-include trending movies (lowered threshold)
        elif movie.get('popularity', 0) >= 10:  # Lowered from 20 to 10
            include = True
            reason = f"Trending (pop: {movie['popularity']:.1f})"
        
        # Tier 3: Include English films with minimal activity
        elif movie.get('original_language') in ['en'] and movie.get('vote_count', 0) >= 3:  # Lowered from 5 to 3
            include = True
            reason = f"English film ({movie['vote_count']} votes)"
        
        # Tier 4: Check for reviews (but don't require them)
        elif title:
            time.sleep(0.15)  # Faster rate limit
            has_review, review_info = check_has_reviews(title, year, config)
            
            if has_review:
                include = True
                review_data = review_info
                parts = []
                if 'rt_score' in review_info:
                    parts.append(f"RT: {review_info['rt_score']}%")
                if 'metacritic' in review_info:
                    parts.append(f"Meta: {review_info['metacritic']}")
                if 'imdb_votes' in review_info:
                    parts.append(f"IMDB: {review_info['imdb_votes']} votes")
                reason = " | ".join(parts)
            else:
                # Tier 5: Very lenient catch-all for any movie with basic data
                if movie.get('title') and movie.get('release_date'):  # Has title and release date
                    include = True
                    reason = "Recent release"
        
        if include:
            included_count += 1
            movie['inclusion_reason'] = reason
            movie['review_data'] = review_data
            curated.append(movie)
            print(f"  ✓ {title[:40]:40} | {reason}")
        else:
            print(f"  ✗ {title[:40]:40} | No qualifying criteria")
    
    print(f"\n{'='*60}")
    print(f"BALANCED RESULTS: {included_count} movies included")
    print(f"Inclusion rate: {included_count/len(all_movies)*100:.1f}%")
    
    # Sort by release date and popularity
    curated.sort(key=lambda x: (
        x.get('release_date', ''),
        x.get('popularity', 0)
    ), reverse=True)
    
    return curated

def get_watch_providers(movie_id, region, api_key):
    """Get streaming providers for a movie"""
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/watch/providers"
    try:
        response = requests.get(url, params={'api_key': api_key})
        data = response.json()
        
        providers = []
        if 'results' in data and region in data['results']:
            region_data = data['results'][region]
            for provider_type in ['flatrate', 'rent', 'buy']:
                if provider_type in region_data:
                    for provider in region_data[provider_type]:
                        name = provider['provider_name']
                        if name not in providers:
                            providers.append(name)
        
        return providers
    except:
        return []

def generate_html(movies):
    """Generate HTML output"""
    os.makedirs('output/site', exist_ok=True)
    
    with open('templates/site.html', 'r') as f:
        template = Template(f.read())
    
    # Process movies for display
    for movie in movies:
        # Add poster URL
        if movie.get('poster_path'):
            movie['poster'] = f"https://image.tmdb.org/t/p/w500{movie['poster_path']}"
        
        # Extract RT score if available
        if 'review_data' in movie and 'rt_score' in movie['review_data']:
            movie['rt_score'] = movie['review_data']['rt_score']
        
        # Build display title with year
        year = movie.get('release_date', '')[:4] if movie.get('release_date') else ''
        movie['year'] = year
        
        # TMDB vote
        movie['tmdb_vote'] = movie.get('vote_average')
        
        # Add URL fields for template
        movie['tmdb_url'] = f"https://www.themoviedb.org/movie/{movie['id']}"
        movie['tmdb_watch_link'] = f"https://www.themoviedb.org/movie/{movie['id']}/watch"
        movie['justwatch_search_link'] = f"https://www.justwatch.com/us/search?q={movie['title'].replace(' ', '%20')}"
    
    html = template.render(
        items=movies,
        site_title="New Release Wall (Balanced)",
        window_label=f"Last {args.days} days",
        region=args.region,
        store_names=[],
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M")
    )
    
    with open('output/site/index.html', 'w') as f:
        f.write(html)
    
    print(f"Generated HTML with {len(movies)} movies")

def main():
    global args
    parser = argparse.ArgumentParser()
    parser.add_argument('--region', default='US')
    parser.add_argument('--days', type=int, default=14)
    parser.add_argument('--max-pages', type=int, default=5)
    args = parser.parse_args()
    
    # Get balanced filtered movies
    movies = get_balanced_releases(
        region=args.region,
        days=args.days,
        max_pages=args.max_pages
    )
    
    # Add streaming providers for ALL movies (not just top 25)
    config = load_config()
    print(f"\nFetching streaming providers for all {len(movies)} movies...")
    for i, movie in enumerate(movies):
        providers = get_watch_providers(movie['id'], args.region, config['tmdb_api_key'])
        movie['providers'] = providers
        if providers:
            print(f"  {movie['title'][:30]:30} | {', '.join(providers[:3])}")
        else:
            print(f"  {movie['title'][:30]:30} | No providers")
        time.sleep(0.2)  # Rate limit every request
    
    # Generate output
    generate_html(movies)
    
    print(f"\n✓ Complete! View at http://localhost:8080")
    print(f"  Found {len(movies)} balanced releases")
    print(f"  {sum(1 for m in movies if m.get('providers'))} have streaming info")

if __name__ == "__main__":
    main()
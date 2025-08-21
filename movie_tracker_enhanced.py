#!/usr/bin/env python3
"""
Enhanced Movie Digital Release Tracker
- Tracks all release types (1, 2, 3, 4)
- Uses provider data comparison to detect actual digital availability
- Catches indie films that might not have reliable Type 4 dates
"""

import json
import requests
import yaml
from datetime import datetime, timedelta
import time
import os

class EnhancedMovieTracker:
    def __init__(self, db_file='movie_tracking_enhanced.json'):
        self.db_file = db_file
        self.db = self.load_database()
        self.config = self.load_config()
        self.api_key = self.config['tmdb_api_key']
        self.omdb_api_key = self.config.get('omdb_api_key')
    
    def load_config(self):
        with open("config.yaml", "r") as f:
            return yaml.safe_load(f)
    
    def load_database(self):
        """Load existing tracking database or create new one"""
        if os.path.exists(self.db_file):
            with open(self.db_file, 'r') as f:
                return json.load(f)
        return {
            'movies': {},
            'last_update': None,
            'last_provider_check': None,
            'stats': {
                'total_tracked': 0,
                'resolved': 0,
                'still_tracking': 0,
                'provider_detected': 0
            }
        }
    
    def save_database(self):
        """Save tracking database to disk"""
        self.db['last_update'] = datetime.now().isoformat()
        
        # Update stats
        movies = self.db['movies']
        self.db['stats'] = {
            'total_tracked': len(movies),
            'resolved': len([m for m in movies.values() if m.get('status') == 'resolved']),
            'still_tracking': len([m for m in movies.values() if m.get('status') == 'tracking']),
            'provider_detected': len([m for m in movies.values() if m.get('detected_via_providers', False)])
        }
        
        with open(self.db_file, 'w') as f:
            json.dump(self.db, f, indent=2)
        
        print(f"💾 Database saved: {self.db['stats']}")
    
    def tmdb_get(self, endpoint, params):
        """Generic TMDB API GET request"""
        url = f"https://api.themoviedb.org/3{endpoint}"
        params['api_key'] = self.api_key
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"API error: {e}")
            return {}
    
    def get_release_info(self, movie_id):
        """Get release dates for a movie - ALL types (1, 2, 3, 4)"""
        url = f"https://api.themoviedb.org/3/movie/{movie_id}/release_dates"
        try:
            response = requests.get(url, params={'api_key': self.api_key})
            data = response.json()
            
            result = {
                'premiere_date': None,      # Type 1
                'limited_date': None,       # Type 2  
                'theatrical_date': None,    # Type 3
                'digital_date': None,       # Type 4
                'earliest_release': None,   # Earliest of any type
                'has_digital': False,
                'release_types_found': []
            }
            
            # Collect all release dates by type
            all_dates = {1: [], 2: [], 3: [], 4: []}
            
            if 'results' in data:
                for country_data in data['results']:
                    for release in country_data.get('release_dates', []):
                        release_type = release.get('type')
                        date = release.get('release_date', '')[:10]
                        
                        if date and release_type in [1, 2, 3, 4]:
                            all_dates[release_type].append(date)
                            if release_type not in result['release_types_found']:
                                result['release_types_found'].append(release_type)
                
                # Find earliest date for each type
                for release_type, dates in all_dates.items():
                    if dates:
                        earliest = min(dates)
                        if release_type == 1:
                            result['premiere_date'] = earliest
                        elif release_type == 2:
                            result['limited_date'] = earliest
                        elif release_type == 3:
                            result['theatrical_date'] = earliest
                        elif release_type == 4:
                            result['digital_date'] = earliest
                
                # Find overall earliest release
                all_release_dates = [d for dates in all_dates.values() for d in dates]
                if all_release_dates:
                    result['earliest_release'] = min(all_release_dates)
                
                result['has_digital'] = bool(result['digital_date'])
            
            return result
        except Exception as e:
            print(f"Error getting release info for {movie_id}: {e}")
            return None
    
    def get_justwatch_providers(self, movie_id):
        """Get JustWatch provider data from TMDB"""
        try:
            url = f"https://api.themoviedb.org/3/movie/{movie_id}/watch/providers"
            response = requests.get(url, params={'api_key': self.api_key})
            data = response.json()
            
            us_data = data.get('results', {}).get('US', {})
            providers = {
                'rent': us_data.get('rent', []),
                'buy': us_data.get('buy', []),
                'flatrate': us_data.get('flatrate', [])
            }
            
            # Check if any digital providers are available
            has_digital_providers = any(providers.values())
            
            return {
                'has_providers': has_digital_providers,
                'providers': providers,
                'provider_count': sum(len(p) for p in providers.values())
            }
        except Exception as e:
            print(f"Error getting providers for {movie_id}: {e}")
            return {'has_providers': False, 'providers': {}, 'provider_count': 0}
    
    def get_omdb_rt_score(self, title, year):
        """Get Rotten Tomatoes score from OMDb API"""
        if not self.omdb_api_key:
            return None
            
        try:
            params = {'apikey': self.omdb_api_key, 't': title}
            if year:
                params['y'] = str(year)
                
            response = requests.get('http://www.omdbapi.com/', params=params)
            data = response.json()
            
            if data.get('Response') == 'True':
                for rating in data.get('Ratings', []):
                    if rating['Source'] == 'Rotten Tomatoes':
                        return int(rating['Value'].rstrip('%'))
        except Exception as e:
            print(f"Error getting RT score for {title}: {e}")
        return None
    
    def comprehensive_bootstrap(self, days_back=730):
        """Bootstrap with comprehensive search for ALL release types"""
        print(f"🚀 Comprehensive bootstrap: scanning {days_back} days for ALL release types...")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Get movies using multiple discovery methods
        all_movies = []
        
        # Method 1: Primary release date (catches most theatrical)
        print("  🎬 Scanning primary releases...")
        movies_primary = self._discover_movies({
            "sort_by": "primary_release_date.desc",
            "primary_release_date.gte": start_date.strftime("%Y-%m-%d"),
            "primary_release_date.lte": end_date.strftime("%Y-%m-%d"),
        })
        all_movies.extend(movies_primary)
        
        # Method 2: Release date (catches premieres, festivals)
        print("  🎪 Scanning all releases...")
        movies_release = self._discover_movies({
            "sort_by": "release_date.desc", 
            "release_date.gte": start_date.strftime("%Y-%m-%d"),
            "release_date.lte": end_date.strftime("%Y-%m-%d"),
        })
        all_movies.extend(movies_release)
        
        # Method 3: Popularity (catches trending indie films)
        print("  📈 Scanning popular recent movies...")
        movies_popular = self._discover_movies({
            "sort_by": "popularity.desc",
            "primary_release_date.gte": (end_date - timedelta(days=365)).strftime("%Y-%m-%d"),
        }, max_pages=10)
        all_movies.extend(movies_popular)
        
        # Deduplicate by TMDB ID
        seen_ids = set()
        unique_movies = []
        for movie in all_movies:
            if movie['id'] not in seen_ids:
                seen_ids.add(movie['id'])
                unique_movies.append(movie)
        
        print(f"  📊 Found {len(unique_movies)} unique movies, analyzing releases...")
        
        # Process each movie
        for i, movie in enumerate(unique_movies):
            if i % 25 == 0:
                print(f"    Processed {i}/{len(unique_movies)} movies...")
            
            movie_id = str(movie['id'])
            if movie_id in self.db['movies']:
                continue  # Already tracking
            
            # Get comprehensive release info
            release_info = self.get_release_info(movie['id'])
            if not release_info or not release_info['earliest_release']:
                continue
            
            # Get provider data
            provider_info = self.get_justwatch_providers(movie['id'])
            
            # Get RT score
            year = None
            if release_info['earliest_release']:
                year = release_info['earliest_release'][:4]
            rt_score = self.get_omdb_rt_score(movie['title'], year)
            
            # Determine status
            status = 'resolved' if (release_info['has_digital'] or provider_info['has_providers']) else 'tracking'
            
            # Add to database
            self.db['movies'][movie_id] = {
                'title': movie['title'],
                'tmdb_id': movie['id'],
                'premiere_date': release_info['premiere_date'],
                'limited_date': release_info['limited_date'],
                'theatrical_date': release_info['theatrical_date'],
                'digital_date': release_info['digital_date'],
                'earliest_release': release_info['earliest_release'],
                'release_types_found': release_info['release_types_found'],
                'provider_count': provider_info['provider_count'],
                'has_providers': provider_info['has_providers'],
                'detected_via_providers': provider_info['has_providers'] and not release_info['has_digital'],
                'rt_score': rt_score,
                'status': status,
                'added_to_db': datetime.now().isoformat()[:10],
                'last_checked': datetime.now().isoformat()[:10],
                'last_provider_check': datetime.now().isoformat()[:10]
            }
            
            time.sleep(0.15)  # Rate limiting
        
        self.save_database()
        print(f"✅ Comprehensive bootstrap complete!")
        print(f"  📊 Total movies: {self.db['stats']['total_tracked']}")
        print(f"  🎯 Provider-detected: {self.db['stats']['provider_detected']}")
    
    def _discover_movies(self, base_params, max_pages=50):
        """Helper to discover movies with pagination"""
        movies = []
        page = 1
        
        while page <= max_pages:
            params = base_params.copy()
            params['page'] = page
            params['region'] = 'US'
            
            data = self.tmdb_get("/discover/movie", params)
            page_movies = data.get("results", [])
            
            if not page_movies:
                break
                
            movies.extend(page_movies)
            total_pages = min(data.get("total_pages", 1), max_pages)
            
            if page >= total_pages:
                break
                
            page += 1
            time.sleep(0.2)
        
        return movies
    
    def check_providers_for_tracking_movies(self):
        """Check provider availability for movies still being tracked"""
        tracking_movies = {k: v for k, v in self.db['movies'].items() 
                          if v['status'] == 'tracking'}
        
        if not tracking_movies:
            print("📭 No movies currently being tracked")
            return 0
        
        print(f"🔍 Checking providers for {len(tracking_movies)} tracking movies...")
        
        newly_available = 0
        for movie_id, movie_data in tracking_movies.items():
            provider_info = self.get_justwatch_providers(int(movie_id))
            
            # Update provider data
            movie_data['provider_count'] = provider_info['provider_count']
            movie_data['has_providers'] = provider_info['has_providers']
            movie_data['last_provider_check'] = datetime.now().isoformat()[:10]
            
            # Check if movie went digital via providers
            if provider_info['has_providers'] and not movie_data.get('has_providers_previously', False):
                movie_data['status'] = 'resolved'
                movie_data['detected_via_providers'] = True
                movie_data['digital_detected_date'] = datetime.now().isoformat()[:10]
                newly_available += 1
                
                print(f"  🎯 {movie_data['title']} - Digital via providers! ({provider_info['provider_count']} providers)")
            
            movie_data['has_providers_previously'] = provider_info['has_providers']
            time.sleep(0.1)
        
        self.db['last_provider_check'] = datetime.now().isoformat()
        print(f"✅ Found {newly_available} newly available via providers")
        return newly_available
    
    def add_movie_by_title(self, title, year=None):
        """Manually add a specific movie to tracking (for missing indie films)"""
        print(f"🔍 Searching for: {title}" + (f" ({year})" if year else ""))
        
        # Search TMDB
        params = {'query': title}
        if year:
            params['year'] = year
            
        data = self.tmdb_get("/search/movie", params)
        movies = data.get('results', [])
        
        if not movies:
            print(f"❌ No movies found for '{title}'")
            return False
        
        # Take the first match (or best match by year)
        movie = movies[0]
        if year:
            for m in movies:
                if m.get('release_date', '').startswith(str(year)):
                    movie = m
                    break
        
        movie_id = str(movie['id'])
        
        if movie_id in self.db['movies']:
            print(f"ℹ️  {movie['title']} already being tracked")
            return True
        
        print(f"➕ Adding: {movie['title']} ({movie.get('release_date', 'Unknown date')})")
        
        # Get full details
        release_info = self.get_release_info(movie['id'])
        provider_info = self.get_justwatch_providers(movie['id'])
        
        # Get RT score
        movie_year = None
        if release_info and release_info['earliest_release']:
            movie_year = release_info['earliest_release'][:4]
        rt_score = self.get_omdb_rt_score(movie['title'], movie_year)
        
        # Determine status
        status = 'resolved' if (release_info['has_digital'] or provider_info['has_providers']) else 'tracking'
        
        # Add to database
        self.db['movies'][movie_id] = {
            'title': movie['title'],
            'tmdb_id': movie['id'],
            'premiere_date': release_info['premiere_date'] if release_info else None,
            'limited_date': release_info['limited_date'] if release_info else None,
            'theatrical_date': release_info['theatrical_date'] if release_info else None,
            'digital_date': release_info['digital_date'] if release_info else None,
            'earliest_release': release_info['earliest_release'] if release_info else None,
            'release_types_found': release_info['release_types_found'] if release_info else [],
            'provider_count': provider_info['provider_count'],
            'has_providers': provider_info['has_providers'],
            'detected_via_providers': provider_info['has_providers'] and not (release_info and release_info['has_digital']),
            'rt_score': rt_score,
            'status': status,
            'added_to_db': datetime.now().isoformat()[:10],
            'last_checked': datetime.now().isoformat()[:10],
            'last_provider_check': datetime.now().isoformat()[:10],
            'manually_added': True
        }
        
        provider_status = f" - {provider_info['provider_count']} providers" if provider_info['has_providers'] else " - No providers yet"
        rt_status = f" (RT: {rt_score}%)" if rt_score else ""
        print(f"✅ Added{provider_status}{rt_status}")
        
        self.save_database()
        return True
    
    def daily_update(self):
        """Enhanced daily update: check TMDB dates + provider availability"""
        print("📅 Running enhanced daily update...")
        
        # Add new theatrical releases
        new_movies = self.add_new_releases(days_back=7)
        
        # Check provider availability for tracking movies
        newly_via_providers = self.check_providers_for_tracking_movies()
        
        # Check TMDB digital dates for tracking movies
        newly_via_tmdb = self.check_tmdb_digital_dates()
        
        self.save_database()
        
        print(f"\n📊 Daily Summary:")
        print(f"  New movies added: {new_movies}")
        print(f"  Digital via providers: {newly_via_providers}")
        print(f"  Digital via TMDB: {newly_via_tmdb}")
        print(f"  Still tracking: {self.db['stats']['still_tracking']}")
        print(f"  Provider-detected total: {self.db['stats']['provider_detected']}")
    
    def add_new_releases(self, days_back=7):
        """Add new releases from multiple discovery methods"""
        print(f"➕ Adding new releases from last {days_back} days...")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Multiple discovery methods
        all_movies = []
        
        # Primary releases
        movies_primary = self._discover_movies({
            'primary_release_date.gte': start_date.strftime('%Y-%m-%d'),
            'primary_release_date.lte': end_date.strftime('%Y-%m-%d'),
            'sort_by': 'popularity.desc'
        }, max_pages=5)
        all_movies.extend(movies_primary)
        
        # All releases
        movies_all = self._discover_movies({
            'release_date.gte': start_date.strftime('%Y-%m-%d'),
            'release_date.lte': end_date.strftime('%Y-%m-%d'),
            'sort_by': 'popularity.desc'
        }, max_pages=5)
        all_movies.extend(movies_all)
        
        # Deduplicate
        seen_ids = set()
        unique_movies = []
        for movie in all_movies:
            if movie['id'] not in seen_ids:
                seen_ids.add(movie['id'])
                unique_movies.append(movie)
        
        new_count = 0
        for movie in unique_movies:
            movie_id = str(movie['id'])
            if movie_id not in self.db['movies']:
                release_info = self.get_release_info(movie['id'])
                if release_info and release_info['earliest_release']:
                    provider_info = self.get_justwatch_providers(movie['id'])
                    
                    # Get RT score
                    year = release_info['earliest_release'][:4]
                    rt_score = self.get_omdb_rt_score(movie['title'], year)
                    
                    status = 'resolved' if (release_info['has_digital'] or provider_info['has_providers']) else 'tracking'
                    
                    self.db['movies'][movie_id] = {
                        'title': movie['title'],
                        'tmdb_id': movie['id'],
                        'premiere_date': release_info['premiere_date'],
                        'limited_date': release_info['limited_date'],
                        'theatrical_date': release_info['theatrical_date'],
                        'digital_date': release_info['digital_date'],
                        'earliest_release': release_info['earliest_release'],
                        'release_types_found': release_info['release_types_found'],
                        'provider_count': provider_info['provider_count'],
                        'has_providers': provider_info['has_providers'],
                        'detected_via_providers': provider_info['has_providers'] and not release_info['has_digital'],
                        'rt_score': rt_score,
                        'status': status,
                        'added_to_db': datetime.now().isoformat()[:10],
                        'last_checked': datetime.now().isoformat()[:10],
                        'last_provider_check': datetime.now().isoformat()[:10]
                    }
                    new_count += 1
                    print(f"  ➕ Added: {movie['title']}")
                
                time.sleep(0.1)
        
        print(f"✅ Added {new_count} new movies")
        return new_count
    
    def check_tmdb_digital_dates(self):
        """Check TMDB digital dates for tracking movies"""
        tracking_movies = {k: v for k, v in self.db['movies'].items() 
                          if v['status'] == 'tracking'}
        
        resolved_count = 0
        for movie_id, movie_data in tracking_movies.items():
            release_info = self.get_release_info(int(movie_id))
            if release_info and release_info['has_digital'] and not movie_data.get('digital_date'):
                # Movie got TMDB digital date!
                movie_data['digital_date'] = release_info['digital_date']
                movie_data['status'] = 'resolved'
                movie_data['last_checked'] = datetime.now().isoformat()[:10]
                resolved_count += 1
                
                print(f"  ✅ {movie_data['title']} - TMDB digital date: {release_info['digital_date']}")
            
            time.sleep(0.1)
        
        return resolved_count
    
    def show_status(self):
        """Show enhanced database status"""
        # Ensure stats exist
        if 'stats' not in self.db:
            self.save_database()  # This will calculate stats
        stats = self.db['stats']
        print(f"\n📊 ENHANCED TRACKING DATABASE STATUS")
        print(f"{'='*50}")
        print(f"Total movies tracked: {stats['total_tracked']}")
        print(f"Resolved (went digital): {stats['resolved']}")
        print(f"  └─ Via provider detection: {stats['provider_detected']}")
        print(f"Still tracking: {stats['still_tracking']}")
        print(f"Last update: {self.db.get('last_update', 'Never')}")
        print(f"Last provider check: {self.db.get('last_provider_check', 'Never')}")
        
        # Show tracking examples
        tracking = {k: v for k, v in self.db['movies'].items() if v.get('status') == 'tracking'}
        if tracking:
            print(f"\nCurrently tracking (sample):")
            for movie_id, movie in list(tracking.items())[:5]:
                earliest = movie.get('earliest_release')
                if earliest:
                    days_since = (datetime.now() - datetime.fromisoformat(earliest)).days
                    types = movie.get('release_types_found', [])
                    type_str = f" (Types: {types})" if types else ""
                    print(f"  • {movie['title']} - {days_since} days since release{type_str}")
        
        # Show provider-detected movies
        provider_detected = {k: v for k, v in self.db['movies'].items() 
                           if v.get('detected_via_providers', False)}
        if provider_detected:
            print(f"\nProvider-detected movies (sample):")
            for movie_id, movie in list(provider_detected.items())[:5]:
                rt_text = f" (RT: {movie.get('rt_score')}%)" if movie.get('rt_score') else ""
                providers = movie.get('provider_count', 0)
                print(f"  🎯 {movie['title']} - {providers} providers{rt_text}")
        
        # Show recently added movies
        recent_added = {k: v for k, v in self.db['movies'].items() 
                       if v.get('manually_added', False)}
        if recent_added:
            print(f"\nManually added movies:")
            for movie_id, movie in recent_added.items():
                status = movie.get('status', 'unknown')
                providers = movie.get('provider_count', 0)
                print(f"  ➕ {movie['title']} - {status} ({providers} providers)")

def main():
    tracker = EnhancedMovieTracker()
    
    import sys
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'bootstrap':
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 730
            tracker.comprehensive_bootstrap(days)
        elif command == 'daily':
            tracker.daily_update()
        elif command == 'status':
            tracker.show_status()
        elif command == 'add':
            if len(sys.argv) < 3:
                print("Usage: python movie_tracker_enhanced.py add 'Movie Title' [year]")
                return
            title = sys.argv[2]
            year = int(sys.argv[3]) if len(sys.argv) > 3 else None
            tracker.add_movie_by_title(title, year)
        elif command == 'check-providers':
            tracker.check_providers_for_tracking_movies()
            tracker.save_database()
        else:
            print("Usage: python movie_tracker_enhanced.py [bootstrap|daily|status|add|check-providers]")
    else:
        tracker.show_status()

if __name__ == "__main__":
    main()
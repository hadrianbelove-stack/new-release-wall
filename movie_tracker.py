#!/usr/bin/env python3
"""
Movie Digital Release Tracker
Maintains a database of movies and tracks when they go digital
"""

import json
import requests
import yaml
from datetime import datetime, timedelta
import time
import os

class MovieTracker:
    def __init__(self, db_file='movie_tracking.json'):
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
            'stats': {
                'total_tracked': 0,
                'resolved': 0,
                'still_tracking': 0
            }
        }
    
    def save_database(self):
        """Save tracking database to disk"""
        self.db['last_update'] = datetime.now().isoformat()
        
        # Update stats
        movies = self.db['movies']
        self.db['stats'] = {
            'total_tracked': len(movies),
            'resolved': len([m for m in movies.values() if m['status'] == 'resolved']),
            'still_tracking': len([m for m in movies.values() if m['status'] == 'tracking'])
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
        """Get release dates for a movie"""
        url = f"https://api.themoviedb.org/3/movie/{movie_id}/release_dates"
        try:
            response = requests.get(url, params={'api_key': self.api_key})
            data = response.json()
            
            result = {
                'theatrical_date': None,
                'digital_date': None,
                'has_digital': False
            }
            
            if 'results' in data:
                for country_data in data['results']:
                    if country_data['iso_3166_1'] == 'US':
                        for release in country_data.get('release_dates', []):
                            release_type = release.get('type')
                            date = release.get('release_date', '')[:10]
                            
                            if release_type == 3:  # Theatrical
                                if not result['theatrical_date'] or date < result['theatrical_date']:
                                    result['theatrical_date'] = date
                            elif release_type == 4:  # Digital
                                if not result['digital_date'] or date < result['digital_date']:
                                    result['digital_date'] = date
                                result['has_digital'] = True
                        break
            
            return result
        except Exception as e:
            print(f"Error getting release info for {movie_id}: {e}")
            return None
    
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
    
    def bootstrap_database(self, days_back=730):
        """Bootstrap database with movies from past N days"""
        print(f"🚀 Bootstrapping database with movies from last {days_back} days...")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        all_movies = []
        page = 1
        total_pages = 999  # Will be updated from API response
        
        while page <= total_pages:
            print(f"  Scanning page {page}...")
            
            params = {
                "sort_by": "primary_release_date.desc",
                "region": "US",
                "primary_release_date.gte": start_date.strftime("%Y-%m-%d"),
                "primary_release_date.lte": end_date.strftime("%Y-%m-%d"),
                "page": page
            }
            
            data = self.tmdb_get("/discover/movie", params)
            all_movies.extend(data.get("results", []))
            
            # Update total_pages from API
            total_pages = min(data.get("total_pages", 1), 500)  # TMDB caps at 500
            
            if page >= total_pages:
                break
                
            page += 1
            time.sleep(0.2)
        
        print(f"  Found {len(all_movies)} movies, checking release status...")
        
        # Add movies to tracking database
        for i, movie in enumerate(all_movies):
            if i % 20 == 0:
                print(f"    Processed {i}/{len(all_movies)} movies...")
            
            movie_id = str(movie['id'])
            if movie_id in self.db['movies']:
                continue  # Already tracking
            
            release_info = self.get_release_info(movie['id'])
            if not release_info:
                continue
            
            # Get RT score
            year = None
            if release_info['theatrical_date']:
                year = release_info['theatrical_date'][:4]
            rt_score = self.get_omdb_rt_score(movie['title'], year)
            
            # Add to database
            self.db['movies'][movie_id] = {
                'title': movie['title'],
                'tmdb_id': movie['id'],
                'theatrical_date': release_info['theatrical_date'],
                'digital_date': release_info['digital_date'],
                'rt_score': rt_score,
                'status': 'resolved' if release_info['has_digital'] else 'tracking',
                'added_to_db': datetime.now().isoformat()[:10],
                'last_checked': datetime.now().isoformat()[:10]
            }
            
            time.sleep(0.1)  # Rate limiting
        
        self.save_database()
        print(f"✅ Bootstrap complete!")
    
    def add_new_theatrical_releases(self, days_back=7):
        """Daily: Add new theatrical releases from last X days"""
        print(f"➕ Adding new releases from last {days_back} days...")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        params = {
            'api_key': self.api_key,
            'primary_release_date.gte': start_date.strftime('%Y-%m-%d'),
            'primary_release_date.lte': end_date.strftime('%Y-%m-%d'),
            'sort_by': 'popularity.desc',
            'page': 1
        }
        
        response = requests.get('https://api.themoviedb.org/3/discover/movie', params=params)
        movies = response.json().get('results', [])
        
        new_count = 0
        for movie in movies:
            movie_id = str(movie['id'])
            if movie_id not in self.db['movies']:
                release_info = self.get_release_info(movie['id'])
                if release_info and release_info['theatrical_date']:
                    # Get RT score
                    year = release_info['theatrical_date'][:4]
                    rt_score = self.get_omdb_rt_score(movie['title'], year)
                    
                    self.db['movies'][movie_id] = {
                        'title': movie['title'],
                        'tmdb_id': movie['id'],
                        'theatrical_date': release_info['theatrical_date'],
                        'digital_date': release_info['digital_date'],
                        'rt_score': rt_score,
                        'status': 'resolved' if release_info['has_digital'] else 'tracking',
                        'added_to_db': datetime.now().isoformat()[:10],
                        'last_checked': datetime.now().isoformat()[:10]
                    }
                    new_count += 1
                    print(f"  ➕ Added: {movie['title']} (RT: {rt_score}%)" if rt_score else f"  ➕ Added: {movie['title']}")
                
                time.sleep(0.1)
        
        print(f"✅ Added {new_count} new movies")
        return new_count
    
    def check_tracking_movies(self):
        """Check digital status for movies still being tracked"""
        tracking_movies = {k: v for k, v in self.db['movies'].items() 
                          if v['status'] == 'tracking'}
        
        if not tracking_movies:
            print("📭 No movies currently being tracked")
            return 0
        
        print(f"🔍 Checking {len(tracking_movies)} movies for digital availability...")
        
        resolved_count = 0
        for movie_id, movie_data in tracking_movies.items():
            release_info = self.get_release_info(int(movie_id))
            if release_info and release_info['has_digital']:
                # Movie went digital!
                movie_data['digital_date'] = release_info['digital_date']
                movie_data['status'] = 'resolved'
                movie_data['last_checked'] = datetime.now().isoformat()[:10]
                resolved_count += 1
                
                print(f"  ✅ {movie_data['title']} went digital: {release_info['digital_date']}")
            else:
                movie_data['last_checked'] = datetime.now().isoformat()[:10]
            
            time.sleep(0.1)
        
        print(f"✅ Found {resolved_count} newly digital movies")
        return resolved_count
    
    def daily_update(self):
        """Run daily update: add new + check existing"""
        print("📅 Running daily update...")
        new_movies = self.add_new_theatrical_releases()
        newly_digital = self.check_tracking_movies()
        self.save_database()
        
        print(f"\n📊 Daily Summary:")
        print(f"  New movies added: {new_movies}")
        print(f"  Movies that went digital: {newly_digital}")
        print(f"  Still tracking: {self.db['stats']['still_tracking']}")
    
    def show_status(self):
        """Show current database status"""
        stats = self.db['stats']
        print(f"\n📊 TRACKING DATABASE STATUS")
        print(f"{'='*40}")
        print(f"Total movies tracked: {stats['total_tracked']}")
        print(f"Resolved (went digital): {stats['resolved']}")
        print(f"Still tracking: {stats['still_tracking']}")
        print(f"Last update: {self.db.get('last_update', 'Never')}")
        
        # Show some examples
        tracking = {k: v for k, v in self.db['movies'].items() if v['status'] == 'tracking'}
        if tracking:
            print(f"\nCurrently tracking (sample):")
            for movie_id, movie in list(tracking.items())[:5]:
                days_since = (datetime.now() - datetime.fromisoformat(movie['theatrical_date'])).days
                print(f"  • {movie['title']} - {days_since} days since theatrical")
        
        recent_digital = {k: v for k, v in self.db['movies'].items() 
                         if v['status'] == 'resolved' and v.get('digital_date')}
        if recent_digital:
            print(f"\nRecently went digital (sample):")
            for movie_id, movie in list(recent_digital.items())[:5]:
                print(f"  • {movie['title']} - Digital: {movie.get('digital_date')}")

def main():
    tracker = MovieTracker()
    
    import sys
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'bootstrap':
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 365
            tracker.bootstrap_database(days)
        elif command == 'daily':
            tracker.daily_update()
        elif command == 'status':
            tracker.show_status()
        else:
            print("Usage: python movie_tracker.py [bootstrap|daily|status]")
    else:
        tracker.show_status()

if __name__ == "__main__":
    main()
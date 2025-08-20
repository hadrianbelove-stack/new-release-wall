#!/bin/bash

# Enable error handling
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Base directory
BASE_DIR="/Users/hadrianbelove/Downloads/new-release-wall"
cd "$BASE_DIR"

# Activate virtual environment
source .venv/bin/activate

# Function to show menu
show_menu() {
    clear
    echo "===================================="
    echo "      NEW RELEASE WALL MENU        "
    echo "===================================="
    echo ""
    echo "1) Run Full Update (Tracking + Scraping)"
    echo "2) Custom Scrape (choose days back)"
    echo "3) Open Website Only (no refresh)"
    echo "4) Database Status"
    echo "5) Stop Server"
    echo "6) Exit"
    echo ""
    echo -n "Choose an option (1-6): "
}

# Function to run full automated update
run_full_update() {
    echo -e "${GREEN}🎬 Running full update...${NC}"
    
    # First, update tracking database automatically
    echo -e "${YELLOW}Updating tracking database...${NC}"
    python3 movie_tracker.py update
    
    # Check for new digital releases from tracking
    echo -e "${YELLOW}Checking for new digital releases...${NC}"
    python3 movie_tracker.py check
    
    # Generate from tracker (last 14 days default)
    python3 generate_from_tracker.py 14
    
    echo -e "${GREEN}✓ Full update complete${NC}"
}

# Function to run custom scraper
run_custom_scrape() {
    echo -n "How many days back to search: "
    read days
    
    echo -e "${GREEN}🎬 Scraping last $days days (no page limit)...${NC}"
    # max-pages 0 means no limit
    python3 new_release_wall_balanced.py --region US --days $days --max-pages 0
    echo -e "${GREEN}✓ Data refreshed${NC}"
}

# Function to show database status
show_status() {
    echo -e "${YELLOW}📊 Database Status:${NC}"
    python3 movie_tracker.py status
    echo ""
    
    # Also show recent discoveries
    echo -e "${YELLOW}Recent Digital Releases:${NC}"
    python3 -c "
import json
try:
    with open('current_releases.json', 'r') as f:
        releases = json.load(f)
    print(f'Found {len(releases)} films that went digital recently')
    for movie in releases[:5]:
        print(f\"  • {movie.get('title')} ({movie.get('year')})\")
except:
    print('No recent releases file found')
"
    echo ""
    echo "Press Enter to continue..."
    read
}

# Function to start server
start_server() {
    echo -e "${GREEN}🌐 Starting web server...${NC}"
    
    # Kill any existing Python servers
    pkill -f "python -m http.server" 2>/dev/null || true
    
    # Start server in background
    cd output/site
    python -m http.server 8000 &
    SERVER_PID=$!
    cd ../..
    
    # Open in browser
    sleep 1
    open http://localhost:8000
    
    echo -e "${GREEN}✓ Server running at http://localhost:8000${NC}"
    echo "Server PID: $SERVER_PID"
}

# Check if tracking database needs bootstrap on first run
check_bootstrap() {
    python3 -c "
import json, os
if not os.path.exists('tracking_db.json'):
    print('NEED_BOOTSTRAP')
else:
    with open('tracking_db.json', 'r') as f:
        db = json.load(f)
    if len(db.get('movies', {})) < 100:
        print('NEED_BOOTSTRAP')
" | grep -q "NEED_BOOTSTRAP" && {
    echo -e "${YELLOW}⚠️  Tracking database needs initialization${NC}"
    echo "Bootstrapping with 2 years of data..."
    python3 movie_tracker.py bootstrap 730
    echo -e "${GREEN}✓ Database initialized${NC}"
    sleep 2
}
}

# Check bootstrap on start
check_bootstrap

# Main loop
while true; do
    show_menu
    read choice
    
    case $choice in
        1)
            run_full_update
            start_server
            ;;
        2)
            run_custom_scrape
            start_server
            ;;
        3)
            start_server
            ;;
        4)
            show_status
            ;;
        5)
            echo -e "${YELLOW}Stopping server...${NC}"
            pkill -f "python -m http.server" 2>/dev/null || true
            echo -e "${GREEN}✓ Server stopped${NC}"
            ;;
        6)
            echo -e "${GREEN}Goodbye!${NC}"
            pkill -f "python -m http.server" 2>/dev/null || true
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid option. Please try again.${NC}"
            sleep 2
            ;;
    esac
    
    if [ "$choice" != "6" ] && [ "$choice" != "4" ]; then
        echo ""
        echo "Press Enter to return to menu..."
        read
    fi
done
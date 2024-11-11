# addon.py
from flask import Flask, jsonify, abort, request
from re import sub
import os
import requests
from bs4 import BeautifulSoup
import logging
from flask_caching import Cache
import re
from typing import Optional, List, Dict, Any

# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure cache (using simple cache for Vercel compatibility)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Configuration
ALLOWED_AGE = int(os.getenv('ALLOWED_AGE', 18))
CONTENT_WEIGHTS = {
    'nudity': {
        'none': 0,     # No nudity
        'minimal': 1,  # Very mild (e.g., swimming)
        'mild': 2,     # Mild suggestive content
        'moderate': 3, # Partial nudity
        'strong': 4    # Explicit content
    },
    'violence': {
        'none': 0,     # No violence
        'minimal': 1,  # Cartoon slapstick
        'mild': 2,     # Mild conflict
        'moderate': 3, # Fighting
        'strong': 4    # Graphic violence
    },
    'profanity': {
        'none': 0,     # No bad language
        'minimal': 1,  # Very mild words
        'mild': 2,     # Mild language
        'moderate': 3, # Strong language
        'strong': 4    # Extreme profanity
    },
    'frightening': {
        'none': 0,     # Not scary
        'minimal': 1,  # Very mild tension
        'mild': 2,     # Mild scary moments
        'moderate': 3, # Frightening scenes
        'strong': 4    # Very disturbing
    },
    'alcohol': {
        'none': 0,     # No alcohol
        'minimal': 1,  # Brief background presence
        'mild': 2,     # References to alcohol
        'moderate': 3, # Alcohol use
        'strong': 4    # Heavy alcohol use
    },
    'spoilers': 0      # No impact on age rating
}

# Keywords for severity detection
SEVERITY_KEYWORDS = {
    'none': ['no', 'none', 'clean', 'family-friendly', 'children'],
    'minimal': ['very mild', 'brief', 'cartoon', 'background', 'distant'],
    'mild': ['mild', 'some', 'minor', 'light', 'suggested'],
    'moderate': ['moderate', 'several', 'blood', 'fighting', 'partial'],
    'strong': ['graphic', 'extreme', 'intense', 'explicit', 'severe']
}

def determine_severity(content: str) -> str:
    """Determine content severity with more granular levels."""
    content_lower = content.lower()
    
    # Check each severity level from strongest to mildest
    for severity in ['strong', 'moderate', 'mild', 'minimal']:
        for keyword in SEVERITY_KEYWORDS[severity]:
            if keyword in content_lower:
                return severity
                
    # If no keywords found or content suggests no issues
    for keyword in SEVERITY_KEYWORDS['none']:
        if keyword in content_lower:
            return 'none'
            
    # Default to minimal if unclear
    return 'minimal'

def calculate_age_rating(sections_data: Dict[str, str]) -> int:
    """Calculate age rating with support for younger audiences."""
    score = 0
    
    for category, content in sections_data.items():
        if not content or category not in CONTENT_WEIGHTS or category == 'spoilers':
            continue
            
        items = [item.strip() for item in content.split('*') if item.strip()]
        
        for item in items:
            severity = determine_severity(item)
            if isinstance(CONTENT_WEIGHTS[category], dict):
                score += CONTENT_WEIGHTS[category].get(severity, 0)
    
    # Enhanced thresholds with support for younger ages
    if score >= 15:
        return 18
    elif score >= 10:
        return 16
    elif score >= 7:
        return 13
    elif score >= 4:
        return 10
    elif score >= 2:
        return 8
    else:
        return 6  # Very mild content suitable for young children

def get_rating_reasons(content: str) -> str:
    """Extract key reasons for age rating with more detail."""
    reasons = []
    
    for category in CONTENT_WEIGHTS.keys():
        if category == 'spoilers':
            continue
            
        # Regex to extract content between category headers
        pattern = f'\\[{category.upper()}\\](.*?)(?=\\[|$)'
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        
        if match and match.group(1).strip():
            severity = determine_severity(match.group(1))
            if severity != 'none':
                reasons.append(f"{category.title()} ({severity})")
    
    return ', '.join(reasons) if reasons else 'Suitable for all ages'

def format_season_episode(id: str) -> str:
    """Format season and episode numbers."""
    try:
        parts = id.split('_')
        season = parts[-2].zfill(2)
        episode = parts[-1].split('-')[0].zfill(2)
        return f"S{season}E{episode}"
    except:
        return "S00E00"

def get_soup(id: str) -> Optional[BeautifulSoup]:
    """Get BeautifulSoup object for IMDB page."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
            'sec-uh-a': '"Not A;Brand";v="99", "Chromium";v="109", "Google Chrome";v="109"',
            'accept-encoding': 'gzip, deflate, br',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'scheme': 'https',
            'authority': 'www.imdb.com'
        }
        page = requests.get(f'https://www.imdb.com/title/{id}/parentalguide', headers=headers)
        soup = BeautifulSoup(page.content, 'html5lib')
        return soup
    except Exception as e:
        logger.error(f"Error in get_soup: {e}")
        return None

def parse_section(soup: Optional[BeautifulSoup]) -> str:
    """Parse a content section."""
    if not soup:
        return ""
    section_comment_tags = soup.find_all('li', {'class': 'ipl-zebra-list__item'})
    section_comment_list = [comment.text.strip() for comment in section_comment_tags]
    comments = cleanup_comments(section_comment_list)
    return comments

def cleanup_comments(comments: List[str]) -> str:
    """Clean up and format comments."""
    clean_comments = []
    if comments:
        for comment in comments:
            cleaned_up = sub(r'\n\n {8}\n {8}\n {12}\n {16}\n {16}\n {12}\nEdit', '', comment)
            clean_comments.append('* ' + cleaned_up)
    return "\n".join(clean_comments)

def display_section(title: str, category: str) -> str:
    """Format a content section."""
    temp = ""
    if category:
        temp += f'\n[{title.upper()}]'
        temp += f'\n{category}\n'
    return temp

@cache.memoize(timeout=3600)
def scrape_movie(id: str) -> List[Any]:
    """Scrape movie/series content advisory information."""
    try:
        soup = get_soup(id)
        if soup:
            soup_sections = soup.find('section', {'class': 'article listo content-advisories-index'})
            if not soup_sections:
                return ["No parental guide available.", "Unknown Title", 0]
            
            soup_nudity = soup_sections.find('section', {'id': 'advisory-nudity'})
            soup_profanity = soup_sections.find('section', {'id': 'advisory-profanity'})
            soup_violence = soup_sections.find('section', {'id': 'advisory-violence'})
            soup_spoilers = soup_sections.find('section', {'id': 'advisory-spoilers'})
            soup_frightening = soup_sections.find('section', {'id': 'advisory-frightening'})
            soup_alcohol = soup_sections.find('section', {'id': 'advisory-alcohol'})
            
            nudity = parse_section(soup_nudity)
            profanity = parse_section(soup_profanity)
            violence = parse_section(soup_violence)
            spoilers = parse_section(soup_spoilers)
            frightening = parse_section(soup_frightening)
            alcohol = parse_section(soup_alcohol)
            
            temp = ""
            temp += display_section('nudity', nudity)
            temp += display_section('profanity', profanity)
            temp += display_section('violence', violence)
            temp += display_section('frightening', frightening)
            temp += display_section('alcohol', alcohol)
            temp += display_section('spoilers', spoilers)
            
            title_tag = soup.find('meta', {'property': 'og:title'})
            title = title_tag['content'][:-7] if title_tag and 'content' in title_tag.attrs else "Unknown Title"
            
            # Calculate age rating
            age_rating = calculate_age_rating({
                'nudity': nudity,
                'profanity': profanity,
                'violence': violence,
                'frightening': frightening,
                'alcohol': alcohol,
                'spoilers': spoilers
            })
            
            return [str(temp), title, age_rating]
    except Exception as e:
        logger.error(f"Error in scrape_movie: {e}")
        return [str(e), "Unknown Title", 0]

@cache.memoize(timeout=3600)
def get_age_rating_for_content(imdb_id: str) -> Optional[int]:
    """Get age rating with caching."""
    data = scrape_movie(imdb_id)
    if len(data) >= 3:
        return data[2]
    return None

def getEpId(seriesID: str) -> Optional[str]:
    """Get episode ID for a series."""
    try:
        parts = seriesID.split('_')
        series, season, episode = parts[0], parts[-2], parts[-1]
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
            'sec-uh-a': '"Not A;Brand";v="99", "Chromium";v="109", "Google Chrome";v="109"',
            'accept-encoding': 'gzip, deflate, br',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'scheme': 'https',
            'authority': 'www.imdb.com'
        }
        req = requests.get(f"https://m.imdb.com/title/{series}/episodes/?season={season}", headers=headers)
        soup = BeautifulSoup(req.content, 'html5lib')
        eplist = soup.find('div', {'id': 'eplist'})
        if not eplist:
            return None
        links = [element['href'] for element in eplist.find_all('a')]
        return links[int(episode)-1].split('/')[2].split('?')[0]
    except Exception as e:
        logger.error(f"Error in getEpId: {e}")
        return None

def respond_with(data: Any, status: int = 200):
    """Create JSON response with CORS headers."""
    resp = jsonify(data)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Headers'] = '*'
    resp.headers['Cache-Control'] = 'public, max-age=40000'
    return resp, status

# Define the manifest
MANIFEST = {
    'id': 'com.beast.getparentsguide',
    'version': '1.3.0',  # Incremented version
    'name': 'Get Parents Guide',
    'description': 'Fetch parents guide and block content based on age rating',
    'catalogs': [
        {
            'type': 'movie',
            'id': 'gpg_movies_catalog',
            'name': 'Filtered Movies Catalog'
        },
        {
            'type': 'series',
            'id': 'gpg_series_catalog',
            'name': 'Filtered Series Catalog'
        },
        {
            'type': 'movie',
            'id': 'gpg_search_movie',
            'name': 'Filtered Movie Search'
        },
        {
            'type': 'series',
            'id': 'gpg_search_series',
            'name': 'Filtered Series Search'
        }
    ],
    'types': ['movie', 'series'],
    'resources': [
        {'name': "meta", 'types': ["series", "movie"], 'idPrefixes': ["gpg"]},
        {'name': 'stream', 'types': ['movie', 'series'], "idPrefixes": ["tt", "gpg"]},
        {'name': 'catalog', 'types': ['movie', 'series'], 'idPrefixes': ['gpg_catalog', 'gpg_search']}
    ]
}

@app.route('/')
def root():
    return respond_with({'status': 'working'})

@app.route('/manifest.json')
def addon_manifest_route():
    return respond_with(MANIFEST)

@app.route('/meta/<type>/<id>.json')
def addon_meta(type, id):
    try:
        imdb_id = id.split('-')[-1]
        data = scrape_movie(imdb_id)
        
        if len(data) < 3:
            raise ValueError("Insufficient data returned from scrape_movie")

        content, title, age_rating = data

        # Check if content is allowed based on age rating
        if age_rating > ALLOWED_AGE:
            logger.info(f"Blocking content '{title}' with age rating {age_rating}")
            return respond_with({
                'error': 'Content blocked due to age restriction',
                'age_rating': age_rating,
                'allowed_age': ALLOWED_AGE
            }, 403)

        # Enhanced metadata
        meta = {
            'id': id,
            'type': type,
            'name': title,
            'description': f"Parent's Guide:\n{content}",
            'ageRating': age_rating,
            'ageRatingReason': get_rating_reasons(content)
        }

        # Format series title
        if type == 'series':
            meta['name'] = f"{title} {format_season_episode(id)}"

        return respond_with({'meta': meta})
    except Exception as e:
        logger.error(f"Error in addon_meta: {e}")
        return respond_with({'error': str(e)}, 500)

@app.route('/stream/<type>/<id>.json')
def addon_stream(type, id):
    try:
        id = id.replace('%3A', '_')
        if 'gpg' in id:
            abort(404)

        # Check age rating before proceeding
        imdb_id = id.split('-')[-1] if '-' in id else id.split('_')[0]
        age_rating = get_age_rating_for_content(imdb_id)

        if age_rating is None or age_rating > ALLOWED_AGE:
            logger.info(f"Blocking stream for content ID '{id}' with age rating {age_rating}")
            return respond_with({
                'error': 'Content blocked due to age restriction',
                'age_rating': age_rating
            }, 403)

        if type == 'series':
            ep_id = getEpId(id)
            if ep_id:
                id = f"{id}-{ep_id}"
            else:
                abort(404)

        streams = {
            "streams": [
                {
                    "name": "Parents Guide",
                    "externalUrl": f"stremio:///detail/{type}/gpg-{id}"
                }
            ]
        }
        return respond_with(streams)
    except Exception as e:
        logger.error(f"Error in addon_stream: {e}")
        return respond_with({'error': str(e)}, 500)

@app.route('/catalog/<type>/<id>.json')
def addon_catalog(type, id):
    """Enhanced catalog endpoint with real IMDb data."""
    try:
        if id == 'gpg_movies_catalog':
            # Fetch popular movies
            items = fetch_imdb_popular('movie')
        elif id == 'gpg_series_catalog':
            # Fetch popular series
            items = fetch_imdb_popular('series')
        elif id == 'gpg_search_movie' or id == 'gpg_search_series':
            # Handle search
            query = request.args.get('query', '')
            if not query:
                return respond_with({'metas': []})
            content_type = 'movie' if 'movie' in id else 'series'
            items = search_imdb(query, content_type)
        else:
            abort(400, description="Invalid catalog ID.")

        # Filter and process items
        filtered_content = []
        for item in items:
            # Get age rating
            age_rating = get_age_rating_for_content(item['id'])

            if age_rating is None or age_rating > ALLOWED_AGE:
                continue

            # Add to filtered content
            filtered_content.append({
                'id': f"gpg-{item['id']}",
                'type': type,
                'name': item['title'],
                'ageRating': age_rating
            })

        return respond_with({'metas': filtered_content})
    except Exception as e:
        logger.error(f"Error in addon_catalog: {e}")
        abort(500, description=str(e))

def fetch_imdb_popular(content_type: str) -> List[Dict[str, str]]:
    """Fetch popular content from IMDb."""
    try:
        # Use IMDb's chart URLs
        url = 'https://www.imdb.com/chart/moviemeter' if content_type == 'movie' else 'https://www.imdb.com/chart/tvmeter'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
            'sec-uh-a': '"Not A;Brand";v="99", "Chromium";v="109", "Google Chrome";v="109"',
            'accept-encoding': 'gzip, deflate, br',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'scheme': 'https',
            'authority': 'www.imdb.com'
        }
        
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.content, 'html5lib')
        
        items = []
        titles = soup.find_all('td', class_='titleColumn')
        
        for title in titles[:50]:  # Limit to top 50
            link = title.find('a')
            if link:
                imdb_id = link['href'].split('/')[2]  # Extract IMDb ID
                name = link.text.strip()
                items.append({
                    'id': imdb_id,
                    'title': name
                })
        
        return items
    except Exception as e:
        logger.error(f"Error fetching IMDb popular content: {e}")
        return []

def search_imdb(query: str, content_type: str) -> List[Dict[str, str]]:
    """Search IMDb for content."""
    try:
        # Construct search URL
        search_url = f'https://www.imdb.com/find?q={query}&s=tt&ttype={"ft" if content_type == "movie" else "tv"}'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
            'sec-uh-a': '"Not A;Brand";v="99", "Chromium";v="109", "Google Chrome";v="109"',
            'accept-encoding': 'gzip, deflate, br',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'scheme': 'https',
            'authority': 'www.imdb.com'
        }
        
        response = requests.get(search_url, headers=headers)
        soup = BeautifulSoup(response.content, 'html5lib')
        
        items = []
        results = soup.find_all('tr', class_='findResult')
        
        for result in results[:20]:  # Limit to first 20 results
            link = result.find('a')
            if link:
                imdb_id = link['href'].split('/')[2]
                title = result.find('td', class_='result_text').text.strip()
                items.append({
                    'id': imdb_id,
                    'title': title
                })
        
        return items
    except Exception as e:
        logger.error(f"Error searching IMDb: {e}")
        return []

@app.errorhandler(403)
def forbidden(error):
    return respond_with({'error': error.description}, 403)

@app.errorhandler(404)
def not_found(error):
    return respond_with({'error': 'Not found'}, 404)

@app.errorhandler(500)
def server_error(error):
    return respond_with({'error': 'Internal server error'}, 500)

#if __name__ == '__main__':
#    port = int(os.environ.get('PORT', 8080))
#    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    app.run()

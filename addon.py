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

# Configure file logging with rotation
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler('addon.log', maxBytes=1000000, backupCount=5)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Configure cache (using simple cache for Vercel compatibility)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Configuration
ALLOWED_AGE = int(os.getenv('ALLOWED_AGE', 13))  # Updated to a more realistic default
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

# Mapping of country-specific ratings to numeric age values
COUNTRY_RATING_MAP = {
    "Australia": "M",
    "Austria": "16",
    "Brazil": "16",
    "Canada": "14A",
    "Chile": "14",
    "China": "17",
    "Finland": "K-16",
    "Germany": "16",
    "Hong Kong": "III",
    "Ireland": "15A",
    "Israel": "16",
    "Lithuania": "N-16",
    "Malaysia": "P16",
    "Netherlands": "16",
    "New Zealand": "M",
    "Philippines": "R-16",
    "Singapore": "M18",
    "South Africa": "16",
    "South Korea": "19",
    "Spain": "16",
    "Sweden": "15",
    "Switzerland": "16",
    "Taiwan": "15+",
    "United Kingdom": "15",
    "United States": "R",
    "Vietnam": "T18"
}

# Mapping of country-specific ratings to numeric age values
# Including both numeric and letter-based ratings
RATING_NUMERIC_MAP = {
    "M": 15,      # Australia
    "16": 16,     # Austria, Brazil, Germany, etc.
    "14A": 14,    # Canada, Ireland
    "14": 14,     # Chile
    "17": 17,     # China
    "K-16": 16,   # Finland, Lithuania
    "III": 18,    # Hong Kong
    "P16": 16,    # Malaysia
    "M18": 18,    # Singapore
    "R-16": 16,   # Philippines
    "19": 19,     # South Korea
    "15": 15,     # Sweden, Taiwan, United Kingdom
    "15+": 15,    # Taiwan
    "R": 17,      # United States
    "T18": 18     # Vietnam
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

def extract_numeric_rating(rating: str) -> Optional[int]:
    """Extract numeric value from rating string."""
    if not rating:
        return None
    # Attempt to find all digits in the rating
    digits = re.findall(r'\d+', rating)
    if digits:
        # Convert the first occurrence to integer
        return int(digits[0])
    else:
        # Handle letter-based ratings
        return RATING_NUMERIC_MAP.get(rating, None)

def calculate_content_age_rating(sections_data: Dict[str, str]) -> int:
    """Calculate age rating based on content categories."""
    score = 0
    
    for category, severity in sections_data.items():
        if not severity or category not in CONTENT_WEIGHTS or category == 'spoilers':
            continue
            
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

def calculate_age_certificates_rating(age_certificates: Dict[str, str]) -> Optional[int]:
    """Calculate average age rating based on age certificates."""
    numeric_ratings = []
    for country, rating in age_certificates.items():
        numeric = extract_numeric_rating(rating)
        if numeric:
            numeric_ratings.append(numeric)
        else:
            logger.warning(f"No numeric mapping found for rating '{rating}' in country '{country}'.")
    
    if numeric_ratings:
        average = sum(numeric_ratings) / len(numeric_ratings)
        return round(average)
    return None

def get_combined_age_rating(content_age: int, certificates_age: Optional[int]) -> int:
    """Combine content-based age rating and certificates-based age rating."""
    if certificates_age:
        combined = (content_age + certificates_age) / 2
        return round(combined)
    return content_age

def get_rating_reasons(raw_ratings: Dict[str, Any]) -> str:
    """Extract key reasons for age rating with more detail."""
    reasons = []
    
    content_categories = raw_ratings.get('content_categories', {})
    
    for category, severity in content_categories.items():
        if category == 'mpa_rating':
            continue
        if severity != 'none':
            reasons.append(f"{category.title()} ({severity})")
    
    return ', '.join(reasons) if reasons else 'Suitable for all ages'

def format_season_episode(id: str) -> str:
    """Format season and episode numbers."""
    try:
        parts = id.split('_')
        if len(parts) < 3:
            logger.error(f"Invalid series ID format: {id}")
            return "S00E00"
        season = parts[-2].zfill(2)
        episode = parts[-1].split('-')[0].zfill(2)
        return f"S{season}E{episode}"
    except Exception as e:
        logger.error(f"Error in format_season_episode: {e}")
        return "S00E00"

def get_soup(id: str) -> Optional[BeautifulSoup]:
    """Get BeautifulSoup object for IMDb parental guide page."""
    try:
        # Construct the full URL with query and fragment
        url = f'https://www.imdb.com/title/{id}/parentalguide/?ref_=tt_stry_pg#certificates'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
            'sec-uh-a': '"Not A;Brand";v="99", "Chromium";v="109", "Google Chrome";v="109"',
            'accept-encoding': 'gzip, deflate, br',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'scheme': 'https',
            'authority': 'www.imdb.com'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html5lib')
        return soup
    except Exception as e:
        logger.error(f"Error in get_soup for ID {id}: {e}")
        return None

def parse_content_rating(soup: BeautifulSoup) -> Dict[str, str]:
    """Parse the content rating section to extract content categories."""
    try:
        # Initialize dictionary to hold categories
        categories = {}
        
        # Define content categories to extract
        content_categories = {
            'nudity': "Sex & Nudity",
            'violence': "Violence & Gore",
            'profanity': "Profanity",
            'alcohol': "Alcohol, Drugs & Smoking",
            'frightening': "Frightening & Intense Scenes"
        }

        # Scrape each category's rating (e.g., mild, severe)
        for key, display_name in content_categories.items():
            # Find the category label
            category_label = soup.find('a', string=re.compile(f'^{display_name}:', re.IGNORECASE))
            if category_label:
                # The severity is likely in the next sibling element
                severity_tag = category_label.find_next('div', class_='ipc-html-content-inner-div')
                if severity_tag:
                    severity_text = severity_tag.text.strip().lower()
                    normalized_severity = determine_severity(severity_text)
                    categories[key] = normalized_severity
                    logger.info(f"Extracted {display_name}: {normalized_severity}")
                else:
                    categories[key] = 'none'
                    logger.info(f"{display_name} severity not found, defaulting to 'none'")
            else:
                categories[key] = 'none'
                logger.info(f"{display_name} label not found, defaulting to 'none'")
        
        return categories
    except Exception as e:
        logger.error(f"Error in parse_content_rating: {e}")
        return {}

def parse_age_certificates(soup: BeautifulSoup) -> Optional[Dict[str, str]]:
    """Parse the age certificates section for various countries."""
    age_certificates = {}
    try:
        certificates_section = soup.find('ul', {'data-testid': 'certificates-container'})
        if certificates_section:
            certificates_items = certificates_section.find_all('li', {'data-testid': 'certificates-item'})
            
            for item in certificates_items:
                country_tag = item.find('span', class_='ipc-metadata-list-item__label')
                if country_tag:
                    country = country_tag.text.strip()
                else:
                    logger.warning("Country tag not found in certificates item.")
                    continue
                
                rating_tags = item.find_all('a', class_='ipc-metadata-list-item__list-content-item')
                ratings = [tag.text.strip() for tag in rating_tags]
                
                if ratings:
                    age_certificates[country] = ratings[0]  # Get the first rating for simplicity
                    logger.info(f"Extracted {country} rating: {ratings[0]}")
                else:
                    logger.warning(f"No rating found for country: {country}")
                    
        else:
            logger.warning("Certificates section not found.")
    except Exception as e:
        logger.error(f"Error in parse_age_certificates: {e}")
        return None
    
    return age_certificates

def scrape_movie(id: str) -> Dict[str, Any]:
    """Scrape movie/series content advisory information including age certification."""
    try:
        soup = get_soup(id)
        if not soup:
            return {
                "content_description": "No parental guide available.",
                "title": "Unknown Title",
                "age_rating": 0,
                "raw_ratings": {}
            }
        
        # Log a snippet of the HTML to verify structure
        snippet = soup.prettify()[:1000]  # Log first 1000 characters
        logger.debug(f"HTML Snippet for ID {id}:\n{snippet}")
        
        # Parse content ratings
        content_categories = parse_content_rating(soup)
        if not content_categories:
            logger.warning(f"No content ratings found for ID {id}.")
        
        # Parse age certificates
        age_certificates = parse_age_certificates(soup)
        if not age_certificates:
            logger.warning(f"No age certificates found for ID {id}.")
        
        # Extract title
        title = "Unknown Title"
        title_tag = soup.find('meta', {'property': 'og:title'})
        if title_tag and 'content' in title_tag.attrs:
            title = title_tag['content'].replace(" Parental Guide | IMDb", "").strip()
        else:
            # Fallback to h1 tag
            h1_tag = soup.find('h1')
            if h1_tag:
                title = h1_tag.text.strip()
            else:
                logger.warning(f"Title not found for ID {id}.")
        
        logger.info(f"Extracted title: {title}")
        
        # Calculate content-based age rating
        content_age_rating = calculate_content_age_rating(content_categories)
        logger.info(f"Content-based age rating for {title}: {content_age_rating}")
        
        # Calculate certificates-based age rating
        certificates_age_rating = calculate_age_certificates_rating(age_certificates)
        if certificates_age_rating:
            logger.info(f"Certificates-based age rating for {title}: {certificates_age_rating}")
        else:
            logger.warning(f"No certificates-based age rating calculated for {title}.")
        
        # Combine both ratings into one average rating
        combined_age_rating = get_combined_age_rating(content_age_rating, certificates_age_rating)
        logger.info(f"Combined age rating for {title}: {combined_age_rating}")
        
        # Compile content description
        content_description = ""
        for category, severity in content_categories.items():
            formatted_category = category.replace('_', ' ').title()
            content_description += f"[{formatted_category}]\n{severity.capitalize()}\n"
        
        if age_certificates:
            content_description += "\n[Age Certificates]\n"
            for country, rating in age_certificates.items():
                content_description += f"{country}: {rating}\n"
        
        logger.debug(f"Content Description:\n{content_description}")
        
        # Prepare raw ratings data
        raw_ratings = {
            'mpa_rating': 'Unknown',  # MPA Rating not scraped from parentalguide
            'content_categories': content_categories,
            'age_certificates': age_certificates if age_certificates else {}
        }
        
        return {
            "content_description": content_description,
            "title": title,
            "age_rating": combined_age_rating,
            "raw_ratings": raw_ratings
        }
    except Exception as e:
        logger.error(f"Error in scrape_movie for ID {id}: {e}")
        return {
            "content_description": str(e),
            "title": "Unknown Title",
            "age_rating": 0,
            "raw_ratings": {}
        }

@cache.memoize(timeout=3600)
def get_age_rating_for_content(imdb_id: str) -> Optional[int]:
    """Get age rating with caching."""
    data = scrape_movie(imdb_id)
    return data.get('age_rating', None)

def getEpId(seriesID: str) -> Optional[str]:
    """Get episode ID for a series."""
    try:
        parts = seriesID.split('_')
        if len(parts) < 3:
            logger.error(f"Invalid series ID format: {seriesID}")
            return None
        series, season, episode = parts[0], parts[-2], parts[-1]
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
            'sec-uh-a': '"Not A;Brand";v="99", "Chromium";v="109", "Google Chrome";v="109"',
            'accept-encoding': 'gzip, deflate, br',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'scheme': 'https',
            'authority': 'www.imdb.com'
        }
        req = requests.get(f"https://www.imdb.com/title/{series}/episodes/?season={season}", headers=headers, timeout=10)
        req.raise_for_status()
        soup = BeautifulSoup(req.content, 'html5lib')
        eplist = soup.find('div', {'id': 'episodes_content'})
        if not eplist:
            logger.warning(f"No episode list found for series ID {series}, season {season}.")
            return None
        links = [element['href'] for element in eplist.find_all('a', href=True) if '/title/' in element['href']]
        if int(episode) - 1 < len(links):
            ep_link = links[int(episode)-1]
            ep_id = ep_link.split('/')[2]
            logger.info(f"Extracted episode ID: {ep_id} for series ID: {series}")
            return ep_id
        else:
            logger.warning(f"Episode {episode} out of range for series ID {series}.")
            return None
    except Exception as e:
        logger.error(f"Error in getEpId for seriesID {seriesID}: {e}")
        return None

def respond_with(data: Any, status: int = 200):
    """Create JSON response with CORS headers."""
    resp = jsonify(data)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Headers'] = '*'
    resp.headers['Cache-Control'] = 'public, max-age=40000'
    resp.headers['Content-Type'] = 'application/json'
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

# Routes
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
        
        if not data:
            raise ValueError("No data returned from scrape_movie")

        content = data.get('content_description', '')
        title = data.get('title', 'Unknown Title')
        age_rating = data.get('age_rating', 0)
        raw_ratings = data.get('raw_ratings', {})
        
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
            'ageRatingReason': get_rating_reasons(raw_ratings),
            'raw_ratings': raw_ratings  # Include raw ratings data
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
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html5lib')
        
        items = []
        titles = soup.find_all('td', class_='titleColumn')
        
        for title in titles[:50]:  # Limit to top 50
            link = title.find('a')
            if link and 'href' in link.attrs:
                imdb_id = link['href'].split('/')[2]  # Extract IMDb ID
                name = link.text.strip()
                items.append({
                    'id': imdb_id,
                    'title': name
                })
        
        logger.info(f"Fetched {len(items)} popular {content_type}s from IMDb.")
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
        
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html5lib')
        
        items = []
        results = soup.find_all('tr', class_='findResult')
        
        for result in results[:20]:  # Limit to first 20 results
            link = result.find('a')
            if link and 'href' in link.attrs:
                imdb_id = link['href'].split('/')[2]
                title_td = result.find('td', class_='result_text')
                title = title_td.text.strip() if title_td else "Unknown Title"
                # Clean title by removing extra info
                title = re.sub(r'\(.*?\)', '', title).strip()
                items.append({
                    'id': imdb_id,
                    'title': title
                })
        
        logger.info(f"Found {len(items)} search results for query '{query}' ({content_type}).")
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

# New Route for Fetching Logs
@app.route('/logs')
def fetch_logs():
    try:
        with open('addon.log', 'r') as log_file:
            logs = log_file.read()
        return respond_with({'logs': logs})
    except Exception as e:
        logger.error(f"Error fetching logs: {e}")
        return respond_with({'error': 'Unable to fetch logs.'}, 500)

# Test Routes

@app.route('/test')
def test_endpoint():
    """Test endpoint that checks basic functionality"""
    try:
        results = {
            'status': 'running',
            'allowed_age': ALLOWED_AGE,
            'tests': []
        }
        
        # Define a list of known test movies with their IMDb IDs and expected age ratings
        test_movies = [
            {'id': 'tt0111161', 'title': 'The Shawshank Redemption', 'expected_age': 15},
            {'id': 'tt0068646', 'title': 'The Godfather', 'expected_age': 18},
            {'id': 'tt0108052', 'title': "Schindler's List", 'expected_age': 16},
            {'id': 'tt1375666', 'title': 'Inception', 'expected_age': 13},
            {'id': 'tt0468569', 'title': 'The Dark Knight', 'expected_age': 13},
            {'id': 'tt0816692', 'title': 'Interstellar', 'expected_age': 13},
            {'id': 'tt0109830', 'title': 'Forrest Gump', 'expected_age': 10},
            {'id': 'tt0137523', 'title': 'Fight Club', 'expected_age': 18},
            {'id': 'tt0167260', 'title': 'The Lord of the Rings: The Return of the King', 'expected_age': 13},
            {'id': 'tt0110912', 'title': 'Pulp Fiction', 'expected_age': 17},
            {'id': 'tt1371734', 'title': 'Gladiator II', 'expected_age': 16},  # Unique ID
            {'id': 'tt0910970', 'title': 'WALL·E', 'expected_age': 6},
        ]
        
        # Test 1: Manifest
        manifest_test = {
            'name': 'Manifest Check',
            'endpoint': '/manifest.json'
        }
        try:
            manifest = MANIFEST
            if not manifest or 'version' not in manifest:
                raise ValueError("Invalid manifest")
            manifest_test['status'] = 'passed'
            manifest_test['details'] = f"Manifest version: {manifest['version']}"
        except Exception as e:
            manifest_test['status'] = 'failed'
            manifest_test['error'] = str(e)
        results['tests'].append(manifest_test)

        # Test 2 to N: Known Movies
        for movie in test_movies:
            movie_test = {
                'name': f"Content Check - {movie['title']}",
                'endpoint': f"/meta/movie/gpg-{movie['id']}"
            }
            try:
                data = scrape_movie(movie['id'])
                if data.get('age_rating', 0) > 0:
                    age_rating = data['age_rating']
                    title = data.get('title', 'Unknown Title')
                    is_allowed = age_rating <= ALLOWED_AGE
                    movie_test['status'] = 'passed' if is_allowed else 'failed'
                    movie_test['details'] = f"{title} age rating: {age_rating} | Expected: {'Allowed' if age_rating <= ALLOWED_AGE else 'Blocked'}"
                else:
                    movie_test['status'] = 'failed'
                    movie_test['error'] = 'Invalid age rating'
            except Exception as e:
                movie_test['status'] = 'failed'
                movie_test['error'] = str(e)
            results['tests'].append(movie_test)

        # Test 3: Search functionality with multiple queries
        search_queries = ['disney', 'action', 'drama', 'comedy']
        for query in search_queries:
            search_test = {
                'name': f'Search Function Check - Query: "{query}"',
                'endpoint': f'/catalog/movie/gpg_search_movie?query={query}'
            }
            try:
                items = search_imdb(query, 'movie')
                search_test['status'] = 'passed' if len(items) > 0 else 'failed'
                search_test['details'] = f'Found {len(items)} items'
                if not items:
                    search_test['error'] = 'No search results found'
            except Exception as e:
                search_test['status'] = 'failed'
                search_test['error'] = str(e)
            results['tests'].append(search_test)

        # Test 4: Catalog functionality for movies and series
        catalog_tests = [
            {'id': 'gpg_movies_catalog', 'type': 'movie', 'description': 'Popular Movies Catalog'},
            {'id': 'gpg_series_catalog', 'type': 'series', 'description': 'Popular Series Catalog'}
        ]
        for catalog in catalog_tests:
            catalog_test = {
                'name': f'Catalog Function Check - {catalog["description"]}',
                'endpoint': f'/catalog/{catalog["type"]}/{catalog["id"]}'
            }
            try:
                items = fetch_imdb_popular(catalog['type'])
                catalog_test['status'] = 'passed' if len(items) > 0 else 'failed'
                catalog_test['details'] = f'Found {len(items)} items'
                if not items:
                    catalog_test['error'] = 'No catalog items found'
            except Exception as e:
                catalog_test['status'] = 'failed'
                catalog_test['error'] = str(e)
            results['tests'].append(catalog_test)

        # Calculate overall status - fail if any test failed
        failed_tests = [t for t in results['tests'] if t['status'] == 'failed']
        results['overall_status'] = 'failed' if failed_tests else 'passed'
        
        return respond_with(results)
    except Exception as e:
        logger.error(f"Error in test_endpoint: {e}")
        return respond_with({
            'status': 'error',
            'error': str(e)
        }, 500)

@app.route('/test/<movie_id>')
def test_movie(movie_id):
    """Test endpoint for specific movie ID"""
    try:
        data = scrape_movie(movie_id)
        if not data or 'age_rating' not in data:
            return respond_with({
                'status': 'error',
                'error': 'Insufficient data'
            }, 400)
            
        content = data.get('content_description', '')
        title = data.get('title', 'Unknown Title')
        age_rating = data.get('age_rating', 0)
        raw_ratings = data.get('raw_ratings', {})
        
        return respond_with({
            'status': 'success',
            'data': {
                'title': title,
                'age_rating': age_rating,
                'rating_reasons': get_rating_reasons(raw_ratings),
                'raw_ratings': raw_ratings,
                'is_allowed': age_rating <= ALLOWED_AGE
            }
        })
    except Exception as e:
        logger.error(f"Error in test_movie: {e}")
        return respond_with({
            'status': 'error',
            'error': str(e)
        }, 500)

@app.route('/test-page')
def test_page():
    """HTML page for testing the addon"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Stremio Parents Guide Addon - Test Dashboard</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 1200px;
                margin: 20px auto;
                padding: 0 20px;
                background: #f5f5f5;
            }
            .test-card {
                background: white;
                padding: 15px;
                margin: 10px 0;
                border-radius: 5px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .status {
                display: inline-block;
                padding: 3px 8px;
                border-radius: 3px;
                color: white;
                font-size: 14px;
                margin-left: 8px;
            }
            .passed { background: #4caf50; }
            .failed { background: #f44336; }
            .loading { background: #2196f3; }
            button {
                background: #2196f3;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
            }
            button:hover {
                background: #1976d2;
            }
            .movie-input {
                padding: 8px;
                margin-right: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                width: 300px;
            }
            #testResults, #movieResults {
                margin-top: 20px;
            }
            .rating-info {
                display: flex;
                gap: 10px;
                align-items: center;
                margin: 10px 0;
            }
            .rating-badge {
                font-size: 24px;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
                color: white;
            }
            .allowed { background: #4caf50; }
            .blocked { background: #f44336; }
            .error { color: #f44336; }
            .raw-data {
                background: #f5f5f5;
                padding: 10px;
                border-radius: 4px;
                margin-top: 10px;
                font-family: monospace;
                white-space: pre-wrap;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }
            th {
                background-color: #f2f2f2;
            }
            .log-section {
                max-height: 200px;
                overflow-y: scroll;
                background: #333;
                color: #fff;
                padding: 10px;
                border-radius: 4px;
                font-family: monospace;
                white-space: pre-wrap;
                margin-top: 10px;
            }
        </style>
    </head>
    <body>
        <h1>Stremio Parents Guide Addon - Test Dashboard</h1>
        
        <div class="test-card">
            <h3>Configuration</h3>
            <p>Allowed Age: <strong id="allowedAge">Loading...</strong></p>
        </div>
    
        <div class="test-card">
            <h3>Run Comprehensive Tests</h3>
            <button onclick="runTests()">Run All Tests</button>
            <div id="testResults">
                <!-- Test results will appear here -->
            </div>
        </div>
    
        <div class="test-card">
            <h3>Test Specific Movie/Series</h3>
            <input type="text" id="movieId" class="movie-input" placeholder="Enter IMDb ID (e.g., tt0910970)">
            <button onclick="testMovie()">Test Movie/Series</button>
            <div id="movieResults">
                <!-- Movie test results will appear here -->
            </div>
        </div>
        
        <div class="test-card">
            <h3>Advanced Debugging Logs</h3>
            <button onclick="fetchLogs()">Fetch Latest Logs</button>
            <div id="debugLogs" class="log-section">
                <!-- Debug logs will appear here -->
            </div>
        </div>
    
        <script>
            function runTests() {
                document.getElementById('testResults').innerHTML = '<p>Running tests...</p>';
                
                fetch('/test')
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`Server error: ${response.statusText}`);
                        }
                        return response.json();
                    })
                    .then(data => {
                        document.getElementById('allowedAge').textContent = data.allowed_age;
                        
                        let html = '<h4>Test Results:</h4>';
                        data.tests.forEach(test => {
                            html += `
                                <div class="test-card">
                                    <h4>${test.name}</h4>
                                    <p>Status: <span class="status ${test.status}">${test.status}</span></p>
                                    <p>Endpoint: ${test.endpoint}</p>
                                    ${test.details ? `<p>Details: ${test.details}</p>` : ''}
                                    ${test.error ? `<p class="error">Error: ${test.error}</p>` : ''}
                                </div>
                            `;
                        });
                        
                        html += `
                            <div class="test-card">
                                <h4>Overall Status</h4>
                                <p><span class="status ${data.overall_status}">${data.overall_status}</span></p>
                            </div>
                        `;
                        
                        document.getElementById('testResults').innerHTML = html;
                    })
                    .catch(error => {
                        document.getElementById('testResults').innerHTML = `
                            <div class="test-card">
                                <p class="error">Error: ${error.message}</p>
                            </div>
                        `;
                        console.error('Test Endpoint Error:', error);
                    });
            }
    
            function testMovie() {
                const movieId = document.getElementById('movieId').value;
                if (!movieId) {
                    alert('Please enter an IMDb ID');
                    return;
                }
    
                document.getElementById('movieResults').innerHTML = '<p>Testing movie/series...</p>';
                
                fetch(`/test/${movieId}`)
                    .then(response => {
                        if (!response.ok) {
                            return response.json().then(data => {
                                throw new Error(data.error || 'Unknown error');
                            });
                        }
                        return response.json();
                    })
                    .then(data => {
                        if (data.status === 'success') {
                            let html = `
                                <div class="test-card">
                                    <h4>${data.data.title}</h4>
                                    <div class="rating-info">
                                        <span class="rating-badge ${data.data.is_allowed ? 'allowed' : 'blocked'}">
                                            ${data.data.age_rating}+
                                        </span>
                                        <span>${data.data.is_allowed ? 'Allowed' : 'Blocked'}</span>
                                    </div>
                                    <p><strong>Rating Reasons:</strong> ${data.data.rating_reasons}</p>
                                    <details>
                                        <summary>Raw Rating Data</summary>
                                        <div class="raw-data">${JSON.stringify(data.data.raw_ratings, null, 2)}</div>
                                    </details>
                                </div>
                            `;
                            document.getElementById('movieResults').innerHTML = html;
                        } else {
                            document.getElementById('movieResults').innerHTML = `
                                <div class="test-card">
                                    <p class="error">Error: ${data.error}</p>
                                </div>
                            `;
                        }
                    })
                    .catch(error => {
                        document.getElementById('movieResults').innerHTML = `
                            <div class="test-card">
                                <p class="error">Error: ${error.message}</p>
                            </div>
                        `;
                        console.error('Test Movie Error:', error);
                    });
            }
            
            function fetchLogs() {
                fetch('/logs')
                    .then(response => response.json())
                    .then(data => {
                        if (data.logs) {
                            document.getElementById('debugLogs').innerText = data.logs;
                        } else if (data.error) {
                            document.getElementById('debugLogs').innerHTML = `<p class="error">${data.error}</p>`;
                        }
                    })
                    .catch(error => {
                        document.getElementById('debugLogs').innerHTML = `
                            <div class="test-card">
                                <p class="error">Error: ${error.message}</p>
                            </div>
                        `;
                        console.error('Fetch Logs Error:', error);
                    });
            }

            // Run tests on page load
            window.onload = runTests;
        </script>
    </body>
    </html>
    """
    return html

if __name__ == '__main__':
    app.run()

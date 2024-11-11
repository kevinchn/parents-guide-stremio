# Stremio Parents Guide Addon

A Stremio addon that provides parental guidance information and age-based content filtering for movies and TV shows.

## Features

- Fetches detailed parental guide information from IMDb
- Age-based content blocking
- Content severity analysis
- Catalog filtering based on age ratings
- Search functionality
- Real-time IMDb data integration

## Installation

### Using the Hosted Version

1. Open Stremio
2. Go to the addons section
3. Click "Community Addons"
4. Enter `https://your-deployment.vercel.app/manifest.json`
5. Click Install

### Local Development

1. Clone the repository:
```bash
git clone https://github.com/yourusername/stremio-parents-guide.git
cd stremio-parents-guide
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run locally:
```bash
python index.py
```

## Environment Variables

- `ALLOWED_AGE`: Maximum allowed age rating (default: 18)
- `PORT`: Server port (default: 8080)

## Deployment

### Deploy to Vercel

1. Install Vercel CLI:
```bash
npm install -g vercel
```

2. Login to Vercel:
```bash
vercel login
```

3. Deploy:
```bash
vercel
```

## API Endpoints

- `/manifest.json`: Addon manifest
- `/meta/<type>/<id>.json`: Content metadata and parental guide
- `/stream/<type>/<id>.json`: Stream information
- `/catalog/<type>/<id>.json`: Content catalogs

## Content Rating System

The addon uses a sophisticated rating system based on:
- Content type (nudity, violence, profanity, etc.)
- Content severity (mild, moderate, strong)
- Frequency of mentions
- Keyword analysis

### Age Ratings

- 18+: Strong adult content
- 16+: Mature content
- 13+: Teen content
- 10+: General audience

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT License - feel free to use this code in your own projects.

## Disclaimer

This addon scrapes data from IMDb. Make sure to comply with IMDb's terms of service when using this addon.

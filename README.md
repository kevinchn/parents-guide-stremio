# Stremio Parents Guide Addon

A **Stremio addon** that provides detailed parental guidance information and age-based content filtering for movies and TV shows. This addon ensures a safer viewing experience by analyzing content severity and blocking inappropriate material based on configurable age ratings.

## Features

- **Fetches Detailed Parental Guide Information from IMDb**
- **Age-Based Content Blocking**
  - Filters content based on age ratings to prevent access to inappropriate material.
- **Content Severity Analysis**
  - Evaluates content categories such as nudity, violence, profanity, frightening scenes, and alcohol use with granular severity levels (`none`, `minimal`, `mild`, `moderate`, `strong`).
- **Catalog Filtering Based on Age Ratings**
  - Ensures that blocked content does not appear in any catalogs.
- **Search Functionality**
  - Allows users to search for movies and TV shows within the allowed age parameters.
- **Real-Time IMDb Data Integration**
  - Scrapes live data from IMDb to provide up-to-date parental guides and content ratings.
- **Comprehensive Testing Suite**
  - Includes API endpoints and an HTML dashboard for verifying addon functionality and performance.

## Features Breakdown

### Age Rating System

The addon uses a sophisticated rating system based on:

- **Content Categories:**
  - Nudity, Violence, Profanity, Frightening Scenes, Alcohol Use, and Spoilers.
- **Severity Levels:**
  - `none`, `minimal`, `mild`, `moderate`, `strong`.
- **Frequency of Mentions:**
  - How often each content type and severity level is mentioned.
- **Keyword Analysis:**
  - Utilizes predefined keywords to determine content severity.

### Age Ratings

Based on the cumulative score from content severity, the addon categorizes content as follows:

- **18+:** Strong adult content.
- **16+:** Mature content.
- **13+:** Teen content.
- **10+:** General audience.
- **8+:** Suitable for older children.
- **6+:** Very mild content suitable for young children.

## Installation

### Using the Hosted Version

1. **Open Stremio:**
   - Launch the Stremio application on your device.

2. **Navigate to Addons:**
   - Go to the addons section within Stremio.

3. **Access Community Addons:**
   - Click on "Community Addons."

4. **Add the Manifest URL:**
   - Enter the following URL:
     ```
     https://your-deployment.vercel.app/manifest.json
     ```
   
5. **Install the Addon:**
   - Click "Install" to add the Parents Guide addon to your Stremio.

### Local Development

1. **Clone the Repository:**
    ```bash
    git clone https://github.com/yourusername/stremio-parents-guide.git
    cd stremio-parents-guide
    ```

2. **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3. **Configure Environment Variables:**
   - Create a `.env` file in the root directory (optional) and set the following variables:
     ```
     ALLOWED_AGE=18
     PORT=8080
     ```

4. **Run Locally:**
    ```bash
    python addon.py
    ```
   - The addon will be accessible at `http://localhost:8080`.

## Environment Variables

- **`ALLOWED_AGE`**: Maximum allowed age rating. Defaults to `18` if not specified.
- **`PORT`**: Server port. Defaults to `8080` if not specified.

## Deployment

### Deploy to Vercel

1. **Install Vercel CLI:**
    ```bash
    npm install -g vercel
    ```

2. **Login to Vercel:**
    ```bash
    vercel login
    ```

3. **Deploy the Addon:**
    ```bash
    vercel
    ```
   - Follow the prompts to deploy your application. After deployment, Vercel will provide a URL where your addon is hosted.

## API Endpoints

### Core Endpoints

- **`/manifest.json`**
  - **Description:** Addon manifest containing metadata and resources.
  - **Method:** `GET`
  - **Response:** JSON object with addon details.

- **`/meta/<type>/<id>.json`**
  - **Description:** Retrieves content metadata and parental guide information.
  - **Parameters:**
    - `type`: `movie` or `series`.
    - `id`: Content ID prefixed with `gpg-` (e.g., `gpg-tt0910970`).
  - **Method:** `GET`
  - **Response:** JSON object containing metadata, age rating, and rating reasons.

- **`/stream/<type>/<id>.json`**
  - **Description:** Provides stream information for allowed content.
  - **Parameters:**
    - `type`: `movie` or `series`.
    - `id`: Content ID prefixed with `gpg-` (e.g., `gpg-tt0910970`).
  - **Method:** `GET`
  - **Response:** JSON object with stream details or error if blocked.

- **`/catalog/<type>/<id>.json`**
  - **Description:** Fetches content catalogs filtered based on age ratings.
  - **Parameters:**
    - `type`: `movie` or `series`.
    - `id`: Catalog ID (e.g., `gpg_movies_catalog`, `gpg_search_movie`).
  - **Method:** `GET`
  - **Response:** JSON object with filtered content metas.

### Testing Endpoints

- **`/test`**
  - **Description:** Runs a series of predefined tests to verify addon functionality.
  - **Method:** `GET`
  - **Response:** JSON object detailing the status of each test and overall status.

- **`/test/<movie_id>`**
  - **Description:** Tests a specific movie by its IMDb ID.
  - **Parameters:**
    - `movie_id`: IMDb ID (e.g., `tt0910970`).
  - **Method:** `GET`
  - **Response:** JSON object with test results for the specified movie.

- **`/test-page`**
  - **Description:** HTML dashboard for viewing test results and addon status.
  - **Method:** `GET`
  - **Response:** Interactive HTML page displaying test results and allowing manual testing.

## Usage Instructions

### Accessing the Test Dashboard

Once deployed, you can access the HTML test dashboard to monitor and verify the addon's functionality.

- **Local Deployment:**
  ```
  http://localhost:8080/test-page
  ```

- **Vercel Deployment:**
  ```
  https://your-app.vercel.app/test-page
  ```

### Using the API Endpoints

- **Run All Tests:**
    ```bash
    curl http://localhost:8080/test
    ```
  
  **Response Example:**
    ```json
    {
        "status": "running",
        "allowed_age": 18,
        "tests": [
            {
                "name": "Manifest Check",
                "endpoint": "/manifest.json",
                "status": "passed",
                "details": "Manifest available"
            },
            {
                "name": "Family Content Check",
                "endpoint": "/meta/movie/gpg-tt0910970",
                "status": "passed",
                "details": "WALL-E age rating: 6"
            },
            {
                "name": "Mature Content Check",
                "endpoint": "/meta/movie/gpg-tt0110912",
                "status": "passed",
                "details": "Pulp Fiction age rating: 16"
            },
            {
                "name": "Search Function Check",
                "endpoint": "/catalog/movie/gpg_search_movie?query=disney",
                "status": "passed",
                "details": "Found 20 items"
            },
            {
                "name": "Catalog Function Check",
                "endpoint": "/catalog/movie/gpg_movies_catalog",
                "status": "passed",
                "details": "Found 50 items"
            }
        ],
        "overall_status": "passed"
    }
    ```

- **Test Specific Movie:**
    ```bash
    curl http://localhost:8080/test/tt0910970
    ```
  
  **Response Example:**
    ```json
    {
        "status": "success",
        "data": {
            "title": "WALL-E",
            "age_rating": 6,
            "rating_reasons": "Suitable for all ages",
            "is_allowed": true
        }
    }
    ```

### Features of the Test Dashboard

- **View Current Configuration:**
  - Displays the current `ALLOWED_AGE` setting.
  
- **Run All Tests:**
  - Triggers all predefined tests and displays their results.
  
- **Test Specific Movies:**
  - Allows you to input an IMDb ID and view detailed test results for that specific movie.
  
- **Visual Status Indicators:**
  - Uses color-coded indicators (`passed`, `failed`, `loading`) for easy identification of test outcomes.

## Content Rating System

The addon employs a detailed content rating system to evaluate and filter content based on parental guidance.

### Rating Components

1. **Content Categories:**
   - **Nudity:** Presence and intensity of nudity.
   - **Violence:** Level and graphic nature of violence.
   - **Profanity:** Use of offensive language.
   - **Frightening:** Scary or disturbing scenes.
   - **Alcohol:** Depiction of alcohol use.
   - **Spoilers:** No impact on age rating.

2. **Severity Levels:**
   - **None:** No mention of the content type.
   - **Minimal:** Very mild or brief mentions.
   - **Mild:** Some or minor mentions.
   - **Moderate:** Several or partial mentions.
   - **Strong:** Graphic, intense, or severe mentions.

### Age Rating Calculation

The addon calculates the age rating based on the cumulative score from content severity across all categories.

- **Scoring Mechanism:**
  - Each content mention contributes to the total score based on its severity.
  
- **Age Thresholds:**
  - **15 and above:** 18+
  - **10 to 14:** 16+
  - **7 to 9:** 13+
  - **4 to 6:** 10+
  - **2 to 3:** 8+
  - **Below 2:** 6+

### Rating Reasons

Provides transparent reasons for the assigned age rating, detailing which content categories and severity levels contributed to the overall rating.

## Contributing

Contributions are welcome! Follow these steps to contribute to the project:

1. **Fork the Repository:**
   - Click the "Fork" button at the top-right of the repository page.

2. **Create a Feature Branch:**
    ```bash
    git checkout -b feature/YourFeatureName
    ```

3. **Commit Your Changes:**
    ```bash
    git commit -m "Add your detailed description here"
    ```

4. **Push to the Branch:**
    ```bash
    git push origin feature/YourFeatureName
    ```

5. **Submit a Pull Request:**
   - Go to your forked repository and click "Compare & pull request."
   - Provide a clear description of your changes and submit the pull request.

## License

This project is licensed under the **MIT License**. Feel free to use and modify this code in your own projects.

## Disclaimer

This addon scrapes data from IMDb. Ensure that you comply with IMDb's [Terms of Service](https://www.imdb.com/conditions) when using this addon. The author is not responsible for any misuse or violations of IMDb's policies.

---

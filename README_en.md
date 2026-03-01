# ParentsHandbook

ParentsHandbook is an LLM-based movie content auditing tool designed to provide intuitive viewing risk assessments for parents, judging whether movie or TV show clips are suitable for their children. The system works by instantly scraping IMDb's Parental Guide data and outsourcing the processing to Google Gemini, ultimately outputting a structured content rating report across four dimensions.

**English Version** | [中文版](README.md)

---

## Core Features

- **Streaming Analysis (SSE)**: Streams LLM-parsed JSON data via Server-Sent Events (SSE), enabling incremental rendering of each dimension. Results "pop" onto the screen like falling dominoes the moment they are parsed.
- **Data Scraping & Degradation**: Scrapes parental guide text directly from IMDb. Contains built-in fault tolerance mechanisms to perform smooth degraded rendering when encountering 202 interceptions.
- **Structured Extraction**: Utilizes Gemini 3 Flash for highly concurrent dimension metric extraction, and Gemini 3 Pro to generate the final overall conclusion.
- **Smart Long-term Caching System**: Movie metadata (poster, year, original title, etc.) and AI analysis results are automatically cached locally, bringing the time for subsequent retrievals of the same movie close to zero. Fully supports scraping both feature films and TV shows from TMDb.
- **Distributed Caching**: Movie metadata and analysis reports are centrally cached in Redis Cloud. The cache key is deterministically generated using the `movie:{title}_{year}` format to ensure global uniqueness and avoid repetitive LLM inference overhead.

---

## Architecture

The system adopts a stateless architecture design, specifically optimized for deployment in the Vercel Serverless environment:

- **Core Framework**: FastAPI (Supports fully asynchronous execution and SSE data streams)
- **Deployment Environment**: Vercel Serverless Functions
- **Persistence Layer**: Redis Cloud (Solves the persistence dilemma caused by the read-only `/tmp` directory in Serverless environments)

### Processing Pipeline

1. **Resolver (`movie_resolver.py`)**: Calls the TMDb API to convert user input terms into a deterministic IMDb ID and extracts the release year.
2. **Scraper (`http_scraper.py`)**: Extracts the raw user-submitted text blocks for the four dimensions of *Sex & Nudity, Violence & Gore, Profanity, and Frightening Scenes* from IMDb.
3. **LLM Reasoner (`llm_reasoner.py`)**: Uses a custom brace-counting parser to intercept and incrementally yield a structured JSON data stream.
4. **API Layer (`api.py`)**: Exposes the `/analyze/stream` endpoint, coordinates reads and writes via `redis-py`, and dumps the final stream data to the client.

---

## Environment Variable Configuration

The following environment variables are required to run this system. Do not write actual values in plain text in the codebase.

```env
# AI & Data Sources
GOOGLE_API_KEY=""
TMDB_API_KEY=""

# Persistent Storage (Redis Cloud)
parents_handbook_REDIS_URL=""

# Authentication
ADMIN_KEY=""  # Required. Used to trigger forced re-audits bypassing the cache on the frontend
```

---

## Local Development Guide

### Prerequisites

- Python 3.9+
- Redis instance (local or cloud)

### Initialization

1. Clone the repository:
```bash
git clone https://github.com/Tyleraltight/ParentsHandbook.git
cd ParentsHandbook
```

### 1. Configure Environment Keys

Create a `.env` file in the root directory and enter your keys:

```env
GOOGLE_API_KEY="your-gemini-api-key"
TMDB_API_KEY="your-tmdb-api-key"
ADMIN_KEY="a-custom-secret-password" # Used to force bypass the cache on the frontend for re-audits
```

### 2. Install Dependencies

It is recommended to use a virtual environment or directly install the required dependencies:

```bash
pip install -r requirements.txt
```

2. Start the local development server:
```bash
python -m uvicorn src.api:app --host 127.0.0.1 --port 8001
```

3. Access the local test address: `http://127.0.0.1:8001`

---

## Usage Guide

1. **Search**: Enter the name of the movie or TV show you want to query in the dark-themed search box (both Chinese and English are supported, e.g., "Inception 2010" or "Breaking Bad"). To prevent ambiguity, you can include the year.
2. **Analyze**: Click Analyze. Once the server finishes capturing, the cover information will appear instantly, followed by the four rating cards popping up sequentially alongside the AI's reasoning process.
3. **Review**: Review the specific **strictly quantified 1-10 scores** in each section, as well as the **exact original quotes** from the source parental guide section. At the bottom is the final parental conclusion given by the model for the entire media piece.
4. **Re-Audit**: As an administrator, if you click the "PARENTSHANDBOOK" header at the top of the page rapidly three times, a hidden window will be brought up. After entering the `ADMIN_KEY` configured in the code to unlock advanced mode, a "Re-Audit" button will appear to force re-running the analysis ignoring the cache.

---

## User Declaration & Disclaimer

- The original IMDb Parental Guide text extracted in this program strictly follows the principle of fair use and is intended solely for personal AI analysis, research, and exchange.
- The application relies on crowdsourced data and the logical aggregation of large language models. For highly controversial audio-visual texts, the system's conclusions should serve only as secondary evidence. Please verify the original text independently to ensure information security.

**Based on ultra-fast fully asynchronous framework architecture | Powered by Google Gemini.**

import json
import os
import asyncio

from fastapi import FastAPI, Query, Header, HTTPException
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from upstash_redis import Redis

from src.movie_resolver import TMDBResolver, TMDBResolutionError
from src.scraper.http_scraper import HttpScraper
from src.llm_reasoner import LLMReasoner
from src.config import settings

# ---------------------------------------------------------------------------
# Application Setup
# ---------------------------------------------------------------------------
app = FastAPI(
    title="ParentsHandbook API",
    description="Analyze movie content for parental guidance using LLMs and IMDb data.",
    version="1.0.0",
)

resolver = TMDBResolver()
scraper = HttpScraper()
reasoner = LLMReasoner()

# Redis initialization with graceful fallback
try:
    redis = Redis.from_env()
except Exception:
    redis = None

# Detect Vercel environment
IS_VERCEL = bool(os.environ.get("VERCEL"))
_base = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(_base, "..", "public" if IS_VERCEL else "static")
if not IS_VERCEL:
    os.makedirs(STATIC_DIR, exist_ok=True)

# Mapping from scraper keys to LLM dim keys
DIM_MAP = {
    "Sex & Nudity":       "sex_and_nudity",
    "Violence & Gore":    "violence_and_gore",
    "Profanity":          "profanity",
    "Frightening Scenes": "frightening_scenes",
}


# ---------------------------------------------------------------------------
# Cache Helpers (Upstash Redis)
# ---------------------------------------------------------------------------
def _cache_key(imdb_id: str) -> str:
    """Normalize cache key to prevent duplicates."""
    return f"movie:{imdb_id.strip().lower()}"


def _sse(event: str, data: dict) -> str:
    """Format a single SSE message."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _get_cache(imdb_id: str) -> dict | None:
    """Read from Redis. Returns None on miss or error."""
    if not redis:
        return None
    try:
        data = redis.get(_cache_key(imdb_id))
        if data is None:
            return None
        return json.loads(data) if isinstance(data, str) else data
    except Exception:
        return None


def _set_cache(imdb_id: str, report: dict):
    """Write to Redis only if analysis is complete and valid."""
    if not redis:
        return
    dims_ok = all(
        report.get(d, {}).get("level", "Unknown") != "Unknown"
        for d in DIM_MAP.values()
    )
    overall_ok = report.get("overall", {}).get("analysis", "") not in ("", "分析超时或失败")
    if dims_ok and overall_ok:
        try:
            redis.set(_cache_key(imdb_id), json.dumps(report, ensure_ascii=False))
        except Exception:
            pass  # Silently skip on Redis failure


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False)
async def root():
    if IS_VERCEL:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/index.html", status_code=307)
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/analyze", summary="Analyze (JSON, backward compatible)")
async def analyze(
    title: str = Query(...),
    refresh: bool = Query(False),
    x_admin_key: str = Header("", alias="X-Admin-Key"),
):
    """Non-streaming JSON endpoint."""
    if refresh and (not settings.admin_key or x_admin_key != settings.admin_key):
        refresh = False

    try:
        imdb_id = await resolver.async_search_movie(title)
    except TMDBResolutionError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Cache hit
    if not refresh:
        cached = _get_cache(imdb_id)
        if cached:
            try:
                meta = await resolver.async_get_movie_meta(imdb_id)
            except Exception:
                meta = {}
            return JSONResponse(content={"imdb_id": imdb_id, "source": "cache", "movie": meta, **cached})

    # Live analysis
    try:
        meta, raw = await asyncio.gather(
            resolver.async_get_movie_meta(imdb_id),
            scraper.async_fetch_parental_guide(imdb_id),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        report = await reasoner.async_parse_all_dimensions(raw)
        report["overall"] = await reasoner.async_generate_overall_analysis(report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    report_to_cache = {"title": meta.get("title", imdb_id), "movie": meta, **report}
    _set_cache(imdb_id, report_to_cache)
    return JSONResponse(content={"imdb_id": imdb_id, "source": "live", **report_to_cache})


@app.get("/analyze/stream", summary="Analyze with per-dimension SSE streaming")
async def analyze_stream(
    title: str = Query(...),
    refresh: bool = Query(False),
    x_admin_key: str = Header("", alias="X-Admin-Key"),
):
    """
    SSE endpoint — streams results as they become available:
      meta   -> movie poster/title (immediate)
      dim    -> one dimension at a time (4 events, as each LLM call completes)
      overall -> final analysis
      done   -> completion signal
    """
    if refresh and (not settings.admin_key or x_admin_key != settings.admin_key):
        refresh = False

    async def generate():
        # 1. Resolve TMDB
        try:
            imdb_id = await resolver.async_search_movie(title)
        except Exception as e:
            yield _sse("error", {"detail": f"Movie not found: {str(e)}"})
            return

        # 2. Cache hit — send all at once
        if not refresh:
            cached = _get_cache(imdb_id)
            if cached:
                meta = cached.pop("movie", None)
                if not meta:
                    print(f"[API] Old cache detected for {imdb_id}, attempting cache heal...")
                    try:
                        meta = await resolver.async_get_movie_meta(imdb_id)
                        if meta:
                            heal_data = {"title": meta.get("title", imdb_id), "movie": meta, **cached}
                            _set_cache(imdb_id, heal_data)
                            print(f"[API] Cache healed for {imdb_id} successfully.")
                    except Exception as e:
                        print(f"[API Warning] Meta fetch failed on cache hit: {e}")
                        meta = {}

                yield _sse("cache", {"imdb_id": imdb_id, "source": "cache", "movie": meta, **cached})
                return

        # 3. Parallel: meta + IMDb scrape
        results = await asyncio.gather(
            resolver.async_get_movie_meta(imdb_id),
            scraper.async_fetch_parental_guide(imdb_id),
            return_exceptions=True
        )

        meta = results[0] if not isinstance(results[0], Exception) else {}
        if isinstance(results[0], Exception):
            print(f"[API Warning] Meta fetch failed: {results[0]}")

        raw = results[1] if not isinstance(results[1], Exception) else {}
        if isinstance(results[1], Exception):
            print(f"[API Warning] IMDb scrape failed: {results[1]}")

        # Push meta immediately
        yield _sse("meta", {"imdb_id": imdb_id, "movie": meta})

        # 4. Single streaming LLM call — yield each dim as its JSON closes
        all_dims = {}
        async for dim_key, dim_result in reasoner.async_stream_dimensions(raw):
            all_dims[dim_key] = dim_result
            yield _sse("dim", {"key": dim_key, **dim_result})

        # 5. Overall analysis (uses completed dims)
        try:
            overall = await reasoner.async_generate_overall_analysis(all_dims)
        except Exception:
            overall = {"analysis": "分析超时或失败", "conclusion": "请重试", "context_tags": ["系统超时"]}

        title_str = meta.get("title", imdb_id) if isinstance(meta, dict) else imdb_id
        report = {"title": title_str, "movie": meta, **all_dims, "overall": overall}
        _set_cache(imdb_id, report)

        yield _sse("overall", overall)
        yield _sse("done", {"source": "live"})

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/health")
async def health():
    return {"status": "ok"}


# Only mount static files for local development (Vercel serves public/ via CDN)
if not IS_VERCEL:
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

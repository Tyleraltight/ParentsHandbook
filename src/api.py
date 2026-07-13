import json
import os
import sys
import asyncio

# Load .env into os.environ so proxy vars (HTTP_PROXY, HTTPS_PROXY, etc.)
# are visible to downstream libraries (e.g. google-genai SDK).
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Query, Header, HTTPException
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import redis as redis_lib

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

# ---------------------------------------------------------------------------
# Redis initialization – Redis Cloud via parents_handbook_REDIS_URL
# ---------------------------------------------------------------------------
_redis_url = os.environ.get("parents_handbook_REDIS_URL", "")

try:
    if _redis_url:
        redis_client = redis_lib.from_url(_redis_url, decode_responses=True)
        redis_client.ping()
        print(f"[Redis] Connected OK  url={_redis_url[:40]}...")
    else:
        redis_client = None
        print("[Redis] SKIP – parents_handbook_REDIS_URL is not set")
except Exception as exc:
    redis_client = None
    print(f"[Redis] Init FAILED: {exc}")

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
# Cache Helpers (Redis Cloud)
# ---------------------------------------------------------------------------
def _cache_key(movie_title: str, year: str = "", lang: str = "zh") -> str:
    """Build a human-readable Redis key like  movie:阿凡达_2009:zh ."""
    name = movie_title.strip()
    yr = year.strip() if year else ""
    tag = f"{name}_{yr}" if yr else name
    return f"movie:{tag}:{lang}"


def _raw_cache_key(raw_input: str, lang: str = "zh") -> str:
    """Build a fast-path index key from raw user input (normalized, lowercased)."""
    normalized = raw_input.strip().lower()
    return f"movie:raw:{normalized}:{lang}"


def _sse(event: str, data: dict) -> str:
    """Format a single SSE message."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _get_cache(movie_title: str, year: str = "", lang: str = "zh") -> dict | None:
    """Read from Redis by canonical movie title + year. Returns None on miss or error."""
    if not redis_client:
        return None
    try:
        data = redis_client.get(_cache_key(movie_title, year, lang))
        if data is None:
            return None
        return json.loads(data) if isinstance(data, str) else data
    except Exception:
        return None


def _get_cache_raw(raw_input: str, lang: str = "zh") -> dict | None:
    """Fast-path: read from Redis by raw user input before any TMDB resolution."""
    if not redis_client:
        return None
    try:
        data = redis_client.get(_raw_cache_key(raw_input, lang))
        if data is None:
            return None
        return json.loads(data) if isinstance(data, str) else data
    except Exception:
        return None


def _set_cache(movie_title: str, year: str, report: dict, raw_input: str = "", lang: str = "zh"):
    """Write to Redis only if analysis is complete and valid.
    Also writes a secondary raw-input index for fast-path cache lookup.
    """
    key = _cache_key(movie_title, year, lang)
    if not redis_client:
        print(f"[Redis] SKIP write – redis client is None  key={key}", flush=True)
        return
    dims_ok = all(
        report.get(d, {}).get("level", "Unknown") != "Unknown"
        for d in DIM_MAP.values()
    )
    overall_ok = report.get("overall", {}).get("analysis", "") not in ("", "分析超时或失败", "Analysis timed out or failed")
    if not (dims_ok and overall_ok):
        print(f"[Redis] SKIP write – validation failed  key={key}  dims_ok={dims_ok}  overall_ok={overall_ok}", flush=True)
        return
    try:
        payload = json.dumps(report, ensure_ascii=False)
        # Write canonical key
        redis_client.set(key, payload)
        # Write raw-input index so future searches skip TMDB entirely
        if raw_input:
            redis_client.set(_raw_cache_key(raw_input, lang), payload)
        print(f"[Redis] SET OK  key={key}  bytes={len(payload)}", flush=True)
    except Exception as exc:
        print(f"[Redis] SET FAILED  key={key}  error={exc}", flush=True)


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
    lang: str = Query("zh"),
    x_admin_key: str = Header("", alias="X-Admin-Key"),
):
    """Non-streaming JSON endpoint."""
    if refresh and (not settings.admin_key or x_admin_key != settings.admin_key):
        refresh = False

    try:
        imdb_id = await resolver.async_search_movie(title, lang)
    except TMDBResolutionError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Always fetch meta first (needed for cache key)
    try:
        meta = await resolver.async_get_movie_meta(imdb_id, lang)
    except Exception:
        meta = {}
    m_title = meta.get("title", title)
    m_year  = meta.get("year", "")

    # Cache hit
    if not refresh:
        cached = _get_cache(m_title, m_year, lang)
        if cached:
            return JSONResponse(content={"imdb_id": imdb_id, "source": "cache", "movie": meta, **cached})

    # Live analysis
    try:
        raw = await scraper.async_fetch_parental_guide(imdb_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        result = await reasoner.async_generate_full_report(raw, lang)
        report = {**result["dimensions"], "overall": result["overall"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    report_to_cache = {"title": m_title, "movie": meta, **report}
    _set_cache(m_title, m_year, report_to_cache, lang=lang)
    return JSONResponse(content={"imdb_id": imdb_id, "source": "live", **report_to_cache})


@app.get("/analyze/stream", summary="Analyze with per-dimension SSE streaming")
async def analyze_stream(
    title: str = Query(...),
    refresh: bool = Query(False),
    lang: str = Query("zh"),
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
        def _log(msg: str):
            """Print with immediate flush so Vercel logs capture it."""
            print(msg, flush=True)

        # Fast-path: check raw-input cache BEFORE any TMDB network call.
        # This makes repeated searches near-instant (Redis lookup only).
        if not refresh:
            raw_cached = _get_cache_raw(title, lang)
            if raw_cached:
                _log(f"[Stream] Raw-cache HIT for '{title}' (lang={lang}) — skipping TMDB")
                yield _sse("cache", {"source": "cache", **raw_cached})
                return

        # Slow path: TMDB resolution (only runs on first search or cache miss)
        try:
            imdb_id, meta = await resolver.async_search_and_get_meta(title, lang)
            _log(f"[Stream] TMDB resolved: {imdb_id}")
        except Exception as e:
            error_detail = f"Movie not found: {str(e)}" if lang == "en" else f"电影未找到: {str(e)}"
            yield _sse("error", {"detail": error_detail})
            return

        m_title = meta.get("title", title)
        m_year  = meta.get("year", "")

        # Secondary cache check via canonical title (handles alias searches)
        if not refresh:
            cached = _get_cache(m_title, m_year, lang)
            if cached:
                _log(f"[Stream] Canonical-cache HIT for '{m_title} {m_year}' (lang={lang})")
                yield _sse("cache", {"imdb_id": imdb_id, "source": "cache", "movie": meta, **cached})
                return

        # Push meta immediately so UI can show poster while LLM runs
        yield _sse("meta", {"imdb_id": imdb_id, "movie": meta})
        _log(f"[Stream] Meta sent for {imdb_id} ({m_title} {m_year})")

        # Scrape IMDb parental guide
        try:
            raw = await scraper.async_fetch_parental_guide(imdb_id)
        except Exception as e:
            _log(f"[Stream ERROR] IMDb scrape failed: {e}")
            error_msg = f"Failed to fetch IMDb data, please try again later. ({type(e).__name__}: {str(e)})" if lang == "en" else f"IMDb 数据抓取失败，请稍后重试。({type(e).__name__}: {str(e)})"
            yield _sse("error", {"detail": error_msg})
            return

        # Single LLM call: all 4 dims + overall in one request
        try:
            result = await reasoner.async_generate_full_report(raw, lang)
            all_dims = result["dimensions"]
            overall  = result["overall"]
            for dim_key, dim_result in all_dims.items():
                yield _sse("dim", {"key": dim_key, **dim_result})
                _log(f"[Stream] Dim sent: {dim_key}")
            _log("[Stream] Overall analysis complete")
        except Exception as e:
            _log(f"[Stream ERROR] LLM analysis failed: {e}")
            error_msg = f"Analysis failed: {str(e)}" if lang == "en" else f"分析失败: {str(e)}"
            yield _sse("error", {"detail": error_msg})
            return

        report = {"title": m_title, "movie": meta, **all_dims, "overall": overall}

        # Write-through: commit to Redis (canonical + raw-input index)
        _log(f"[Stream] Writing cache for {m_title}_{m_year} (raw='{title}', lang={lang})")
        _set_cache(m_title, m_year, report, raw_input=title, lang=lang)

        yield _sse("overall", overall)
        yield _sse("done", {"source": "live"})
        _log(f"[Stream] Done for {m_title}_{m_year}")

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/health")
async def health():
    return {"status": "ok"}


# Only mount static files for local development (Vercel serves public/ via CDN)
if not IS_VERCEL:
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

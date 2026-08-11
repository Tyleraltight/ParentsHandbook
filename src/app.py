# Vercel entrypoint — re-exports the FastAPI app instance
from src.api.server import app  # noqa: F401

"""Fund Watch single FastAPI entrypoint for Vercel.

Vercel's FastAPI integration treats a recognized root entrypoint as one
serverless application, allowing FastAPI itself to route /api/* requests.
The existing api.index app contains the core API implementation; auxiliary
P0 product routes are registered via a side-effect import below.
"""
from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.index import app

# Register the expanded P0 analytics/decision endpoints.
import api.p0_routes  # noqa: F401,E402

ROOT = Path(__file__).resolve().parent

# Static assets live at repository root. API routes remain owned by FastAPI.
app.mount(
    "/static",
    StaticFiles(directory=str(ROOT), check_dir=False),
    name="static",
)

@app.get("/", include_in_schema=False)
def frontend_index():
    return FileResponse(ROOT / "index.html")

@app.get("/styles.css", include_in_schema=False)
def frontend_styles():
    return FileResponse(ROOT / "styles.css", media_type="text/css")

@app.get("/app-v2.js", include_in_schema=False)
def frontend_app():
    return FileResponse(ROOT / "app-v2.js", media_type="application/javascript")

@app.get("/app.js", include_in_schema=False)
def frontend_legacy_app():
    return FileResponse(ROOT / "app-v2.js", media_type="application/javascript")

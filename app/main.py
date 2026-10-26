"""FastAPI server: the web page and one API endpoint. Start: .venv/bin/python -m uvicorn app.main:app --port 8000"""

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.agent import CoachError, coach
from app.config import APP_DIR, Limits

STATIC = APP_DIR / "static"

app = FastAPI(title="Customs")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class Ask(BaseModel):
    situation: str = ""


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/favicon.ico")
def favicon():
    return FileResponse(STATIC / "logo.svg", media_type="image/svg+xml")


@app.get("/api/limits")
def limits():
    return {"max_situation_chars": Limits.max_situation_chars}


@app.post("/api/coach")
async def coach_endpoint(ask: Ask, request: Request):
    visitor = request.client.host if request.client else "unknown"
    try:
        return await coach(ask.situation, visitor=visitor)
    except CoachError as exc:
        return JSONResponse({"error": str(exc), "visa": exc.visa, "usage": getattr(exc, "usage", None),
                             "trail": getattr(exc, "trail", [])}, status_code=exc.status)

import os
import random
import hashlib
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from proxy import forward

app = FastAPI(title="CinemaAbyss Proxy (Strangler Fig)")

PORT = int(os.getenv("PORT", "8000"))
MONOLITH_URL = os.getenv("MONOLITH_URL", "http://monolith:8080")
MOVIES_SERVICE_URL = os.getenv("MOVIES_SERVICE_URL", "http://movies-service:8081")
EVENTS_SERVICE_URL = os.getenv("EVENTS_SERVICE_URL", "http://events-service:8082")

GRADUAL_MIGRATION = os.getenv("GRADUAL_MIGRATION", "true").lower() == "true"
MOVIES_MIGRATION_PERCENT = int(os.getenv("MOVIES_MIGRATION_PERCENT", "50"))
MOVIES_MIGRATION_PERCENT = max(0, min(100, MOVIES_MIGRATION_PERCENT))

def pick_backend_for_movies(user_id: str | None) -> str:
    if not GRADUAL_MIGRATION or MOVIES_MIGRATION_PERCENT == 0:
        return MONOLITH_URL
    if MOVIES_MIGRATION_PERCENT == 100:
        return MOVIES_SERVICE_URL
    if user_id:
        digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16) % 100
    else:
        bucket = random.randint(0, 99)
    return MOVIES_SERVICE_URL if bucket < MOVIES_MIGRATION_PERCENT else MONOLITH_URL

@app.get("/healthz")
async def healthz():
    return {"status": True}

@app.api_route("/api/movies{full_path:path}", methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS","HEAD"])
async def movies_proxy(full_path: str, request: Request):
    base = pick_backend_for_movies(request.headers.get("X-User-Id"))
    target = f"{base}/api/movies{full_path}"
    resp = await forward(request, target)
    # Пытаемся проставить заголовок даже при JSONResponse-ошибке
    try:
        resp.headers["X-Proxy-Backend"] = "movies" if base == MOVIES_SERVICE_URL else "monolith"
    except Exception:
        pass
    return resp

@app.api_route("/api/events{full_path:path}", methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS","HEAD"])
async def events_proxy(full_path: str, request: Request):
    target = f"{EVENTS_SERVICE_URL}/api/events{full_path}"
    resp = await forward(request, target)
    try:
        resp.headers["X-Proxy-Backend"] = "events"
    except Exception:
        pass
    return resp

@app.api_route("/api/{rest_of_path:path}", methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS","HEAD"])
async def monolith_fallback(rest_of_path: str, request: Request):
    target = f"{MONOLITH_URL}/api/{rest_of_path}"
    resp = await forward(request, target)
    try:
        resp.headers["X-Proxy-Backend"] = "monolith"
    except Exception:
        pass
    return resp

@app.get("/")
async def root():
    return JSONResponse({"name": "CinemaAbyss Proxy", "routes": ["/api/* -> monolith", "/api/movies -> strangler %", "/healthz"]})

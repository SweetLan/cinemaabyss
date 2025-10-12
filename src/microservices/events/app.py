from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Events Service (stub)", version="1.0")

@app.get("/health")
def health():
    return {"status": "ok", "service": "events"}

# простая заглушка /api/events
@app.api_route("/api/events", methods=["GET", "POST"])
@app.api_route("/api/events/{subpath:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def events_stub(request: Request, subpath: str = ""):
    return JSONResponse({"ok": True, "note": "stub events service", "path": subpath})

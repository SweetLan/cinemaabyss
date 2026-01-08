import os, hashlib
from fastapi import Request

GRADUAL_MIGRATION = os.getenv("GRADUAL_MIGRATION", "true").lower() == "true"
MOVIES_MIGRATION_PERCENT = int(os.getenv("MOVIES_MIGRATION_PERCENT", "50"))

def _hash_to_bucket(value: str) -> int:
    return int(hashlib.md5(value.encode("utf-8")).hexdigest()[:8], 16) % 100

def pick_backend_for_movies(request: Request) -> bool:
    if not GRADUAL_MIGRATION:
        return False
    headers = request.headers
    sticky = (
        headers.get("x-user-id")
        or headers.get("authorization")
        or headers.get("x-request-id")
        or (request.client.host if request.client else "anon")
        or "anon"
    )
    bucket = _hash_to_bucket(sticky)
    return bucket < max(0, min(100, MOVIES_MIGRATION_PERCENT))

def build_target_url(base: str, path: str, query: str) -> str:
    base = base.rstrip("/")
    path = path if path.startswith("/") else f"/{path}"
    return f"{base}{path}" + (f"?{query}" if query else "")

def copy_headers(src_headers) -> dict:
    hop = {"host","connection","keep-alive","proxy-authenticate","proxy-authorization",
           "te","trailers","transfer-encoding","upgrade","content-length"}
    return {k: v for k, v in src_headers.items() if k.lower() not in hop}

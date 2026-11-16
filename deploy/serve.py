"""Serve the production Vue bundle and existing API on the Studio port."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "web/backend"
DATA = Path(os.environ.get("STUDIO_DATA_DIR", "/mnt/workspace/topic5-web"))
DATA.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///" + (DATA / "governance.sqlite").as_posix())
os.environ.setdefault("BENCHMARK_ARTIFACT_ROOT", str(DATA / "artifacts"))
os.environ.setdefault("BENCHMARK_DELIVERY_STAGING_ROOT", str(DATA / "deliveries"))
os.environ.setdefault("GOVERNANCE_ASSISTANT_PROVIDER", "stub")
os.environ.setdefault("GOVERNANCE_SKILL_RUNTIME_MODE", "off")
os.environ.setdefault("TOPIC1_VALUE_QA_AUTO_ENSURE", "false")
os.environ.setdefault("TOPIC2_RISK_DETECT_METHOD", "keyword")
os.chdir(BACKEND)
sys.path.insert(0, str(BACKEND))
from app.main import app
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles


class Frontend(StaticFiles):
    async def get_response(self, path, scope):
        # Missing API endpoints/assets must remain 404 instead of becoming HTML.
        first = path.lstrip("/").split("/", 1)[0]
        if first in {"api", "health", "docs", "redoc", "openapi.json"}:
            raise HTTPException(404)
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or Path(path).suffix or scope["method"] not in {"GET", "HEAD"}:
                raise
            return await super().get_response("index.html", scope)


class HttpMethodOverride:
    """Function Compute allows GET/POST; preserve normal API route permissions."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] == "POST" and scope["path"].startswith("/api/"):
            method = dict(scope.get("headers", [])).get(b"x-http-method-override", b"").upper()
            if method in {b"PUT", b"PATCH", b"DELETE"}:
                scope = dict(scope, method=method.decode("ascii"))
        await self.app(scope, receive, send)


app.add_middleware(HttpMethodOverride)
app.mount("/", Frontend(directory=ROOT / "web/frontend/dist", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "7860")))

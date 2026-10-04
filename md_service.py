"""/health, /config and /help of a MessyDesk service (the same file in each Python service).

/config serves service.json, with the adapter of the storage mode (elg_fs on disk, elg over HTTP,
see md_storage.py) and the runtime overrides SERVICE_ID, SERVICE_NAME, SERVICE_ADAPTER and
SERVICE_LOCAL_URL. MD-consumers registers the service from it. /help serves help/index.md, the
user help that MessyDesk shows for the service.

    import md_service
    md_service.add_routes(app)
"""
import json
import os
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import PlainTextResponse

import md_storage

HERE = Path(__file__).resolve().parent
DESCRIPTOR_PATH = Path(os.getenv("SERVICE_DESCRIPTOR_PATH", HERE / "service.json"))
HELP_PATH = Path(os.getenv("SERVICE_HELP_PATH", HERE / "help" / "index.md"))


def descriptor() -> dict:
    try:
        data = json.loads(DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as err:
        raise HTTPException(status_code=500, detail=f"Descriptor not found: {DESCRIPTOR_PATH}") from err
    except json.JSONDecodeError as err:
        raise HTTPException(status_code=500, detail=f"Descriptor is not valid JSON: {err}") from err
    if not isinstance(data, dict) or not str(data.get("id") or "").strip():
        raise HTTPException(status_code=500, detail="Descriptor must be an object with an id")
    overrides = {
        "id": os.getenv("SERVICE_ID"),
        "name": os.getenv("SERVICE_NAME"),
        # elg_fs in disk mode, elg in HTTP mode, unless SERVICE_ADAPTER says otherwise
        "adapter": os.getenv("SERVICE_ADAPTER") or md_storage.storage_adapter(),
        "local_url": os.getenv("SERVICE_LOCAL_URL"),
    }
    for key, value in overrides.items():
        if value and value.strip():
            data[key] = value.strip()
    return data


def help_markdown() -> str:
    if not HELP_PATH.is_file():
        raise HTTPException(status_code=404, detail="Help file not found")
    return HELP_PATH.read_text(encoding="utf-8")


def add_routes(app) -> None:
    """Adds /config and /help, and /health unless the service has its own."""
    if not any(getattr(route, "path", None) == "/health" for route in app.routes):
        @app.get("/health")
        def health():
            return {"status": "ok", "service": descriptor()["id"]}

    @app.get("/config")
    def config():
        return descriptor()

    @app.get("/help", response_class=PlainTextResponse)
    def help_page():
        return help_markdown()

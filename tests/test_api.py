"""dewarp in HTTP and disk mode, and /config, /help, /health. Runs the real model on CPU."""

import importlib
import io
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "test" / "page.png"
sys.path.insert(0, str(ROOT))


def tilted_photo(path: Path) -> bytes:
    """The sample page seen at an angle on a dark table, as a JPEG photo."""
    import cv2

    page = cv2.imread(str(SAMPLE))
    h, w = page.shape[:2]
    table = np.full((h + 200, w + 200, 3), 40, np.uint8)
    corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    seen = np.float32([[160, 60], [w + 40, 120], [w + 120, h + 160], [60, h + 120]])
    warped = cv2.warpPerspective(page, cv2.getPerspectiveTransform(corners, seen), (w + 200, h + 200), dst=table, borderMode=cv2.BORDER_TRANSPARENT)
    ok, jpeg = cv2.imencode(".jpg", warped)
    path.write_bytes(jpeg.tobytes())
    return jpeg.tobytes()


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    from fastapi.testclient import TestClient

    os.chdir(tmp_path_factory.mktemp("work"))  # uploads/ and output/
    os.environ["UVDOC_MODEL"] = str(ROOT / "model" / "best_model.pkl")
    import api

    return TestClient(api.app)


@pytest.fixture()
def md(tmp_path, monkeypatch):
    (tmp_path / "data/messydesk/projects/p1").mkdir(parents=True)
    tilted_photo(tmp_path / "data/messydesk/projects/p1/photo.jpg")
    monkeypatch.setenv("MD_PATH", str(tmp_path))
    monkeypatch.delenv("STORAGE_MODE", raising=False)
    import md_storage

    importlib.reload(md_storage)
    yield tmp_path
    monkeypatch.delenv("MD_PATH")
    importlib.reload(md_storage)


FILE = {"@rid": "#80:1", "label": "photo.jpg", "path": "data/messydesk/projects/p1/photo.jpg"}


def message(task="dewarp", name="message"):
    return {name: ("message.json", json.dumps({"task": {"id": task}, "file": FILE}), "application/json")}


def test_dewarp_over_http_keeps_png(client):
    response = client.post("/process", files={**message(), "content": ("page.png", SAMPLE.read_bytes(), "image/png")})
    assert response.status_code == 200, response.text
    uri = response.json()["response"]["uri"]
    assert uri.endswith(".png")
    image = Image.open(io.BytesIO(client.get(uri).content))
    assert image.format == "PNG" and image.size == Image.open(SAMPLE).size
    assert client.get(uri).status_code == 404  # removed once fetched


def test_dewarp_on_disk_flattens_a_tilted_photo(client, md):
    response = client.post("/process", files=message())
    assert response.status_code == 200, response.text
    entry = response.json()["response"]["files"][0]
    assert (entry["label"], entry["type"], entry["extension"]) == ("photo.jpg.jpg", "image", "jpg")
    out = np.asarray(Image.open(md / "data/messydesk/tmp" / entry["path"]).convert("L"), dtype=np.float32)
    before = np.asarray(Image.open(md / "data/messydesk/projects/p1/photo.jpg").convert("L"), dtype=np.float32)
    assert out.shape == before.shape
    # the dark table around the tilted page is mostly gone: the result is mostly page
    assert (out < 60).mean() < (before < 60).mean() / 2


def test_old_request_field_and_bad_input(client):
    upload = {"content": ("page.png", SAMPLE.read_bytes(), "image/png")}
    assert client.post("/process", files={**message(name="request"), **upload}).status_code == 200
    assert client.post("/process", files={**message(task="flatten"), **upload}).status_code == 400
    bad = client.post("/process", files={**message(), "content": ("x.jpg", b"not an image", "image/jpeg")})
    assert bad.status_code == 400


def test_config_help_health(client, md):
    config = client.get("/config").json()
    assert config["id"] == "md-uvdoc" and config["adapter"] == "elg_fs" and list(config["tasks"]) == ["dewarp"]
    assert client.get("/help").text.startswith("# UVDoc")
    assert client.get("/health").json()["status"] == "ok"

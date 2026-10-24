"""The interface revalidates its page; hashed assets are cached for good."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.frontend_files import HASHED_ASSETS, REVALIDATE, FrontendFiles


def test_pages_revalidate_and_hashed_assets_are_cached(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "sw.js").write_text("// worker", encoding="utf-8")
    (tmp_path / "assets" / "index-abc123.js").write_text("// app", encoding="utf-8")
    app = FastAPI()
    app.mount("/", FrontendFiles(directory=str(tmp_path), html=True), name="frontend")
    client = TestClient(app)

    assert client.get("/").headers["cache-control"] == REVALIDATE
    assert client.get("/sw.js").headers["cache-control"] == REVALIDATE
    assert (
        client.get("/assets/index-abc123.js").headers["cache-control"] == HASHED_ASSETS
    )

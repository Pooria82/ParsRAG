"""Serve the built interface so an update shows on the next load.

The page, the service worker, and the manifest are revalidated on every load
(``no-cache``), so a browser never keeps an old interface after an update.
Files under ``assets/`` have a content hash in their name, so they are cached
for a year and never revalidated.
"""

import os
from typing import Any

from starlette.responses import Response
from starlette.staticfiles import StaticFiles

HASHED_ASSETS = "public, max-age=31536000, immutable"
REVALIDATE = "no-cache"


class FrontendFiles(StaticFiles):
    """``StaticFiles`` with cache headers suited to a hashed Vite build."""

    def file_response(
        self, full_path: str | os.PathLike[str], *args: Any, **kwargs: Any
    ) -> Response:
        """Add ``Cache-Control`` by file kind."""
        response = super().file_response(full_path, *args, **kwargs)
        parent = os.path.basename(os.path.dirname(os.fspath(full_path)))
        response.headers["Cache-Control"] = (
            HASHED_ASSETS if parent == "assets" else REVALIDATE
        )
        return response

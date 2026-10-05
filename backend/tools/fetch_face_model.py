"""Download the pinned Face Landmarker model and the sample test portrait (AC1.11.2).

    uv run python -m tools.fetch_face_model            # into var/models/ (git-ignored)
    uv run python -m tools.fetch_face_model --dest DIR

Both files are checked against their pinned SHA-256; a file already present with the right
hash is not downloaded again. Nothing is committed: the model is Google's published
``face_landmarker.task`` (float16, version 1) and the portrait is MediaPipe's own published
sample image, used only by the backend tests as one real face (unit-test instructions).
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import urllib.request
from pathlib import Path

from app.face.model import MODEL_SHA256, MODEL_URL, file_sha256

PORTRAIT_URL = "https://storage.googleapis.com/mediapipe-assets/portrait.jpg"
PORTRAIT_SHA256 = "a6f11efaa834706db23f275b6115058fa87fc7f14362681e6abe14e82749de3e"

DEFAULT_DEST = Path("var/models")
TIMEOUT_SECONDS = 120
FILES = (
    ("face_landmarker.task", MODEL_URL, MODEL_SHA256),
    ("portrait.jpg", PORTRAIT_URL, PORTRAIT_SHA256),
)


def fetch(url: str, target: Path, sha256: str) -> bool:
    """Download ``url`` to ``target`` unless it is already there; returns True if fetched.

    Raises:
        RuntimeError: When the download fails or the hash does not match.
    """
    if target.is_file() and file_sha256(target) == sha256:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False, suffix=".part") as temp:
        temp_path = Path(temp.name)
        try:
            # The URL is a fixed https constant above, not user input.
            with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
                while chunk := response.read(1024 * 1024):
                    temp.write(chunk)
        except OSError as exc:
            temp_path.unlink(missing_ok=True)
            raise RuntimeError(f"download failed for {url}: {exc}") from exc
    if file_sha256(temp_path) != sha256:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"SHA-256 mismatch for {url}; refusing the file")
    temp_path.replace(target)
    return True


def main(argv: list[str] | None = None) -> int:
    """Fetch every pinned file into ``--dest``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    args = parser.parse_args(argv)
    for name, url, sha256 in FILES:
        target = args.dest / name
        try:
            fetched = fetch(url, target, sha256)
        except RuntimeError as exc:
            print(f"fetch_face_model: {exc}", file=sys.stderr)
            return 1
        print(f"{'downloaded' if fetched else 'up to date'}: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

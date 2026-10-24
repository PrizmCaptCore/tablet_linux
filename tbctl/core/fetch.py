# SPDX-License-Identifier: GPL-2.0-only
from __future__ import annotations

import hashlib
import shutil
import time
import urllib.request
from pathlib import Path

from tbctl.core.process import BuildError, log


def download(url: str, dest: Path, retries: int = 5) -> Path:
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    log(f"downloading {url}")
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
            tmp.rename(dest)
            return dest
        except OSError as e:
            log(f"download failed ({e}), retry {attempt}/{retries}")
            time.sleep(5)
    raise BuildError(f"could not download {url}")


def file_digest(path: Path, algorithm: str) -> str:
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

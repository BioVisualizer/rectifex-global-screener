from pathlib import Path
import os
from platformdirs import user_cache_dir

APP_ID = "com.rectifex.GlobalScreener"  # must match your Flatpak app-id

def _cache_root() -> Path:
    # Allow override for dev/testing
    override = os.environ.get("RECTIFEX_CACHE_DIR")
    if override:
        return Path(override)
    # Respect XDG inside/outside Flatpak
    return Path(user_cache_dir(appname=APP_ID))

class Cache:
    def __init__(self) -> None:
        self.base_dir = _cache_root()
        self.prices_dir = self.base_dir / "prices"
        self.images_dir = self.base_dir / "images"
        self.prices_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)

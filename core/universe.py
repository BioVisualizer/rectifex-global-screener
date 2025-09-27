"""Utilities for loading and caching equity universes."""

from __future__ import annotations

from dataclasses import dataclass
import gzip
import io
from pathlib import Path
import time

import pandas as pd
import requests


DEFAULT_UNIVERSE = "us-all"
DEFAULT_REFRESH_SECS = 7 * 24 * 3600


@dataclass(frozen=True)
class UniverseSpec:
    """Describe which universe to load and how to cache it."""

    name: str = DEFAULT_UNIVERSE
    max_count: int | None = None
    refresh_secs: int = DEFAULT_REFRESH_SECS


class UniverseLoader:
    """Load ticker universes from free public sources with caching."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def load(self, spec: UniverseSpec) -> pd.Series:
        cache_file = self.cache_dir / f"{spec.name}.csv"
        if cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age < spec.refresh_secs:
                series = pd.read_csv(cache_file)["symbol"]
                return series.iloc[: spec.max_count] if spec.max_count else series

        if spec.name == "us-all":
            series = self._load_us_all()
        elif spec.name == "sp500":
            series = self._load_sp500()
        elif spec.name == "nasdaq":
            series = self._load_nasdaq_only()
        elif spec.name == "nyse":
            series = self._load_nyse_only()
        elif spec.name == "custom":
            series = self._load_custom(cache_file)
        else:  # pragma: no cover - guarded by CLI/UI options
            raise ValueError(f"Unknown universe: {spec.name}")

        processed = self._postprocess_symbols(series)
        processed.iloc[: spec.max_count].to_frame("symbol").to_csv(cache_file, index=False)
        return processed.iloc[: spec.max_count] if spec.max_count else processed

    # ------------------------------------------------------------------
    # Universe sources
    # ------------------------------------------------------------------
    def _load_us_all(self) -> pd.Series:
        nasdaq = self._download_csv_like(
            "https://ftp.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt",
            sep="|",
        )
        other = self._download_csv_like(
            "https://ftp.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
            sep="|",
        )

        nasdaq.columns = [col.lower() for col in nasdaq.columns]
        other.columns = [col.lower() for col in other.columns]

        sym1 = nasdaq.get("symbol") or nasdaq.get("nasdaq symbol")
        sym2 = other.get("symbol") or other.get("act symbol")

        combined = pd.concat([sym1, sym2], ignore_index=True).dropna().astype(str).str.upper()
        return combined.drop_duplicates()

    def _load_nasdaq_only(self) -> pd.Series:
        df = self._download_csv_like(
            "https://ftp.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt",
            sep="|",
        )
        df.columns = [col.lower() for col in df.columns]
        sym = df.get("symbol") or df.get("nasdaq symbol")
        return sym.dropna().astype(str).str.upper().drop_duplicates()

    def _load_nyse_only(self) -> pd.Series:
        df = self._download_csv_like(
            "https://ftp.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
            sep="|",
        )
        df.columns = [col.lower() for col in df.columns]
        sym = df.get("symbol") or df.get("act symbol")
        return sym.dropna().astype(str).str.upper().drop_duplicates()

    def _load_sp500(self) -> pd.Series:
        tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        frame = tables[0]
        column = "Symbol" if "Symbol" in frame.columns else "Ticker symbol"
        return frame[column].astype(str).str.upper().drop_duplicates()

    def _load_custom(self, path: Path) -> pd.Series:
        if path.exists():
            return pd.read_csv(path)["symbol"].astype(str).str.upper().drop_duplicates()
        return pd.Series(dtype=str)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _download_csv_like(self, url: str, sep: str = ",") -> pd.DataFrame:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        content = response.content
        if url.endswith(".gz") or content[:2] == b"\x1f\x8b":
            content = gzip.decompress(content)
        buffer = io.StringIO(content.decode("utf-8", errors="replace"))
        return pd.read_csv(buffer, sep=sep)

    def _postprocess_symbols(self, series: pd.Series) -> pd.Series:
        cleaned = series[~series.str.contains(r"[\^=]", regex=True)]
        cleaned = cleaned[~cleaned.str.contains(r"\$", regex=True)]
        cleaned = cleaned[~cleaned.str.contains(r"\.", regex=True)]
        cleaned = cleaned.str.replace(".", "-", regex=False)
        cleaned = cleaned.drop_duplicates().sort_values(kind="stable").reset_index(drop=True)
        return cleaned


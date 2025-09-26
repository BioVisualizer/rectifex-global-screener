"""Configuration defaults for the Rectifex Global Screener."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class CacheConfig:
    """Configuration for the on-disk price cache."""

    ttl_days: int = 7
    base_dir: str = "cache"
    prices_subdir: str = "prices"
    index_name: str = "index.db"


@dataclass(frozen=True)
class FetcherConfig:
    """Configuration controlling market data fetching behaviour."""

    batch_chunk_size: int = 60
    max_retries: int = 3
    initial_backoff_seconds: float = 1.0
    backoff_factor: float = 2.0
    period_default: str = "1y"


@dataclass(frozen=True)
class ProfilesConfig:
    """Weight profiles used by composite scoring modules."""

    lti_profiles: Dict[str, Dict[str, int]] = field(
        default_factory=lambda: {
            "balanced": {"quality": 35, "growth": 25, "value": 20, "finance": 15, "dividend": 5},
            "quality": {"quality": 45, "growth": 20, "value": 15, "finance": 15, "dividend": 5},
            "growth": {"quality": 25, "growth": 40, "value": 15, "finance": 15, "dividend": 5},
            "income": {"quality": 25, "growth": 15, "value": 15, "finance": 20, "dividend": 25},
        }
    )


@dataclass(frozen=True)
class AppConfig:
    """Root configuration object aggregating subsystem defaults."""

    cache: CacheConfig = CacheConfig()
    fetcher: FetcherConfig = FetcherConfig()
    profiles: ProfilesConfig = ProfilesConfig()


DEFAULT_CONFIG = AppConfig()
"""Singleton default configuration for simple imports."""

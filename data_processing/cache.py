"""
Query result caching module for NHS Patient Pathway Analysis.

Provides file-based caching for Snowflake query results with TTL-based invalidation.
Supports different TTLs for historical data vs data including the current date.

Cache keys are generated from query hashes. Results are stored as compressed JSON.

Usage:
    from data_processing.cache import QueryCache, get_cache

    cache = get_cache()

    # Check for cached result
    result = cache.get(query, params)
    if result is None:
        # Execute query and cache result
        result = execute_query(query, params)
        cache.set(query, params, result, includes_current_data=False)
"""

from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from typing import Any, Optional
import gzip
import hashlib
import json
import os
import time

from config import get_snowflake_config, CacheConfig
from core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class CacheEntry:
    """Metadata for a cached query result."""
    cache_key: str
    query_hash: str
    created_at: datetime
    expires_at: datetime
    includes_current_data: bool
    row_count: int
    file_size_bytes: int
    file_path: Path


@dataclass
class CacheStats:
    """Statistics about the cache."""
    enabled: bool
    cache_dir: Path
    total_entries: int
    total_size_mb: float
    max_size_mb: int
    oldest_entry: Optional[datetime]
    newest_entry: Optional[datetime]
    hit_count: int
    miss_count: int


class QueryCache:
    """
    File-based cache for Snowflake query results.

    Results are stored as gzipped JSON files with TTL-based expiration.
    Supports different TTLs for historical vs current data.

    Attributes:
        config: CacheConfig with cache settings
        cache_dir: Path to cache directory
    """

    def __init__(self, config: Optional[CacheConfig] = None, base_path: Optional[Path] = None):
        """
        Initialize the query cache.

        Args:
            config: Optional CacheConfig. If not provided, loads from snowflake.toml
            base_path: Base path for relative cache directory. Defaults to cwd.
        """
        if config is None:
            sf_config = get_snowflake_config()
            config = sf_config.cache

        self._config = config
        self._base_path = base_path or Path.cwd()

        # Resolve cache directory
        cache_dir = Path(config.directory)
        if not cache_dir.is_absolute():
            cache_dir = self._base_path / cache_dir
        self._cache_dir = cache_dir

        # Stats tracking (in-memory only, reset on restart)
        self._hit_count = 0
        self._miss_count = 0

        # Ensure cache directory exists if enabled
        if self._config.enabled:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def config(self) -> CacheConfig:
        """Return the cache configuration."""
        return self._config

    @property
    def cache_dir(self) -> Path:
        """Return the cache directory path."""
        return self._cache_dir

    @property
    def is_enabled(self) -> bool:
        """Return True if caching is enabled."""
        return self._config.enabled

    def _generate_cache_key(self, query: str, params: Optional[tuple] = None) -> str:
        """
        Generate a cache key from query and parameters.

        Uses SHA256 hash of query + params to create unique key.
        """
        # Normalize query (strip whitespace, lowercase)
        normalized_query = " ".join(query.lower().split())

        # Combine query and params
        key_content = normalized_query
        if params:
            key_content += "|" + "|".join(str(p) for p in params)

        # Hash to create key
        hash_obj = hashlib.sha256(key_content.encode("utf-8"))
        return hash_obj.hexdigest()[:32]  # Use first 32 chars for readability

    def _get_cache_file_path(self, cache_key: str) -> Path:
        """Get the file path for a cache entry."""
        return self._cache_dir / f"{cache_key}.json.gz"

    def _get_meta_file_path(self, cache_key: str) -> Path:
        """Get the metadata file path for a cache entry."""
        return self._cache_dir / f"{cache_key}.meta.json"

    def _is_expired(self, meta: dict) -> bool:
        """Check if a cache entry is expired based on its metadata."""
        expires_at = datetime.fromisoformat(meta["expires_at"])
        return datetime.now() > expires_at

    def get(
        self,
        query: str,
        params: Optional[tuple] = None,
        check_expiry: bool = True
    ) -> Optional[list[dict]]:
        """
        Get a cached query result.

        Args:
            query: SQL query string
            params: Optional query parameters
            check_expiry: If True, returns None for expired entries

        Returns:
            Cached result as list of dicts, or None if not cached/expired
        """
        if not self.is_enabled:
            self._miss_count += 1
            return None

        cache_key = self._generate_cache_key(query, params)
        cache_file = self._get_cache_file_path(cache_key)
        meta_file = self._get_meta_file_path(cache_key)

        # Check if files exist
        if not cache_file.exists() or not meta_file.exists():
            self._miss_count += 1
            logger.debug(f"Cache miss (not found): {cache_key}")
            return None

        # Load and check metadata
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)

            if check_expiry and self._is_expired(meta):
                self._miss_count += 1
                logger.debug(f"Cache miss (expired): {cache_key}")
                return None

            # Load cached data
            with gzip.open(cache_file, "rt", encoding="utf-8") as f:
                data = json.load(f)

            self._hit_count += 1
            logger.info(f"Cache hit: {cache_key} ({meta['row_count']} rows)")
            return data

        except (json.JSONDecodeError, KeyError, OSError) as e:
            logger.warning(f"Cache read error for {cache_key}: {e}")
            self._miss_count += 1
            # Clean up corrupted entry
            self._delete_entry(cache_key)
            return None

    def set(
        self,
        query: str,
        params: Optional[tuple],
        data: list[dict],
        includes_current_data: bool = False,
        custom_ttl_seconds: Optional[int] = None
    ) -> Optional[CacheEntry]:
        """
        Cache a query result.

        Args:
            query: SQL query string
            params: Optional query parameters
            data: Query result as list of dicts
            includes_current_data: If True, uses shorter TTL for current data
            custom_ttl_seconds: Optional custom TTL (overrides config)

        Returns:
            CacheEntry with metadata, or None if caching disabled/failed
        """
        if not self.is_enabled:
            return None

        cache_key = self._generate_cache_key(query, params)
        cache_file = self._get_cache_file_path(cache_key)
        meta_file = self._get_meta_file_path(cache_key)

        # Determine TTL
        if custom_ttl_seconds is not None:
            ttl = custom_ttl_seconds
        elif includes_current_data:
            ttl = self._config.ttl_current_data_seconds
        else:
            ttl = self._config.ttl_seconds

        now = datetime.now()
        expires_at = datetime.fromtimestamp(now.timestamp() + ttl)

        try:
            # Write compressed data
            with gzip.open(cache_file, "wt", encoding="utf-8", compresslevel=6) as f:
                json.dump(data, f, default=str)

            file_size = cache_file.stat().st_size

            # Write metadata
            meta = {
                "cache_key": cache_key,
                "query_hash": hashlib.sha256(query.encode()).hexdigest()[:16],
                "created_at": now.isoformat(),
                "expires_at": expires_at.isoformat(),
                "includes_current_data": includes_current_data,
                "row_count": len(data),
                "file_size_bytes": file_size,
                "ttl_seconds": ttl,
            }

            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)

            logger.info(f"Cached {len(data)} rows as {cache_key} (expires in {ttl}s)")

            # Check if we need to enforce size limit
            self._enforce_size_limit()

            return CacheEntry(
                cache_key=cache_key,
                query_hash=str(meta["query_hash"]),
                created_at=now,
                expires_at=expires_at,
                includes_current_data=includes_current_data,
                row_count=len(data),
                file_size_bytes=file_size,
                file_path=cache_file,
            )

        except (OSError, TypeError) as e:
            logger.error(f"Failed to cache result: {e}")
            return None

    def invalidate(self, query: str, params: Optional[tuple] = None) -> bool:
        """
        Invalidate a specific cache entry.

        Args:
            query: SQL query string
            params: Optional query parameters

        Returns:
            True if entry was deleted, False if not found
        """
        cache_key = self._generate_cache_key(query, params)
        return self._delete_entry(cache_key)

    def _delete_entry(self, cache_key: str) -> bool:
        """Delete a cache entry by key."""
        cache_file = self._get_cache_file_path(cache_key)
        meta_file = self._get_meta_file_path(cache_key)

        deleted = False

        if cache_file.exists():
            cache_file.unlink()
            deleted = True

        if meta_file.exists():
            meta_file.unlink()
            deleted = True

        if deleted:
            logger.debug(f"Deleted cache entry: {cache_key}")

        return deleted

    def clear(self) -> int:
        """
        Clear all cache entries.

        Returns:
            Number of entries deleted
        """
        if not self._cache_dir.exists():
            return 0

        count = 0
        for file in self._cache_dir.glob("*.json*"):
            try:
                file.unlink()
                count += 1
            except OSError as e:
                logger.warning(f"Failed to delete {file}: {e}")

        # Reset stats
        self._hit_count = 0
        self._miss_count = 0

        logger.info(f"Cleared {count} cache files")
        return count // 2  # Divide by 2 since we have .json.gz and .meta.json

    def clear_expired(self) -> int:
        """
        Remove expired cache entries.

        Returns:
            Number of expired entries deleted
        """
        if not self._cache_dir.exists():
            return 0

        count = 0
        for meta_file in self._cache_dir.glob("*.meta.json"):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)

                if self._is_expired(meta):
                    cache_key = meta_file.stem.replace(".meta", "")
                    self._delete_entry(cache_key)
                    count += 1
            except (OSError, json.JSONDecodeError):
                # Delete corrupted metadata files
                cache_key = meta_file.stem.replace(".meta", "")
                self._delete_entry(cache_key)
                count += 1

        logger.info(f"Cleared {count} expired cache entries")
        return count

    def _get_total_size_mb(self) -> float:
        """Calculate total cache size in MB."""
        if not self._cache_dir.exists():
            return 0.0

        total_bytes = sum(
            f.stat().st_size
            for f in self._cache_dir.glob("*")
            if f.is_file()
        )
        return total_bytes / (1024 * 1024)

    def _enforce_size_limit(self) -> int:
        """
        Enforce cache size limit by removing oldest entries.

        Returns:
            Number of entries removed
        """
        max_size_mb = self._config.max_size_mb
        current_size_mb = self._get_total_size_mb()

        if current_size_mb <= max_size_mb:
            return 0

        # Get all entries sorted by creation time
        entries = []
        for meta_file in self._cache_dir.glob("*.meta.json"):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                entries.append((
                    meta_file.stem.replace(".meta", ""),
                    datetime.fromisoformat(meta["created_at"]),
                    meta.get("file_size_bytes", 0)
                ))
            except (OSError, json.JSONDecodeError, KeyError):
                # Clean up corrupted entry
                cache_key = meta_file.stem.replace(".meta", "")
                self._delete_entry(cache_key)

        # Sort by creation time (oldest first)
        entries.sort(key=lambda x: x[1])

        # Remove oldest entries until under limit
        removed = 0
        size_to_remove_bytes = (current_size_mb - max_size_mb * 0.9) * 1024 * 1024  # Target 90% of limit
        removed_bytes = 0

        for cache_key, created_at, file_size in entries:
            if removed_bytes >= size_to_remove_bytes:
                break

            self._delete_entry(cache_key)
            removed_bytes += file_size
            removed += 1

        logger.info(f"Removed {removed} cache entries to enforce size limit")
        return removed

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        if not self._cache_dir.exists():
            return CacheStats(
                enabled=self.is_enabled,
                cache_dir=self._cache_dir,
                total_entries=0,
                total_size_mb=0.0,
                max_size_mb=self._config.max_size_mb,
                oldest_entry=None,
                newest_entry=None,
                hit_count=self._hit_count,
                miss_count=self._miss_count,
            )

        entries = []
        for meta_file in self._cache_dir.glob("*.meta.json"):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                entries.append(datetime.fromisoformat(meta["created_at"]))
            except (OSError, json.JSONDecodeError, KeyError):
                pass

        oldest = min(entries) if entries else None
        newest = max(entries) if entries else None

        return CacheStats(
            enabled=self.is_enabled,
            cache_dir=self._cache_dir,
            total_entries=len(entries),
            total_size_mb=self._get_total_size_mb(),
            max_size_mb=self._config.max_size_mb,
            oldest_entry=oldest,
            newest_entry=newest,
            hit_count=self._hit_count,
            miss_count=self._miss_count,
        )

    def list_entries(self) -> list[CacheEntry]:
        """List all cache entries with metadata."""
        if not self._cache_dir.exists():
            return []

        entries = []
        for meta_file in self._cache_dir.glob("*.meta.json"):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)

                cache_key = meta["cache_key"]
                entries.append(CacheEntry(
                    cache_key=cache_key,
                    query_hash=meta.get("query_hash", ""),
                    created_at=datetime.fromisoformat(meta["created_at"]),
                    expires_at=datetime.fromisoformat(meta["expires_at"]),
                    includes_current_data=meta.get("includes_current_data", False),
                    row_count=meta.get("row_count", 0),
                    file_size_bytes=meta.get("file_size_bytes", 0),
                    file_path=self._get_cache_file_path(cache_key),
                ))
            except (OSError, json.JSONDecodeError, KeyError):
                pass

        # Sort by creation time (newest first)
        entries.sort(key=lambda x: x.created_at, reverse=True)
        return entries


# Module-level singleton
_default_cache: Optional[QueryCache] = None


def get_cache(config: Optional[CacheConfig] = None) -> QueryCache:
    """
    Get a QueryCache instance (creates singleton on first call).

    Args:
        config: Optional CacheConfig. If provided, creates new cache with
                this config. If None, uses/creates default cache.

    Returns:
        QueryCache instance
    """
    global _default_cache

    if config is not None:
        # Custom config requested, create new cache
        return QueryCache(config)

    if _default_cache is None:
        _default_cache = QueryCache()

    return _default_cache


def reset_cache() -> None:
    """Reset the default cache singleton."""
    global _default_cache
    _default_cache = None


def is_cache_enabled() -> bool:
    """Return True if caching is enabled in configuration."""
    config = get_snowflake_config()
    return config.cache.enabled


# Export public API
__all__ = [
    "QueryCache",
    "CacheEntry",
    "CacheStats",
    "get_cache",
    "reset_cache",
    "is_cache_enabled",
]

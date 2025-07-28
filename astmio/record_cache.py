from typing import Dict

from astmio.dataclasses import RecordConfig
from astmio.logging import get_logger

log = get_logger(__name__)


class RecordClassCache:
    """Changed here - Cache for generated Pydantic classes to avoid regeneration."""

    _cache: Dict[str, type] = {}
    _cache_stats = {"hits": 0, "misses": 0}

    @classmethod
    def get_or_create(cls, record_config: RecordConfig, factory_func) -> type:
        """Get cached class or create new one."""
        cache_key = cls.get_cache_key(record_config)

        if cache_key in cls._cache:
            cls._cache_stats["hits"] += 1
            log.debug(f"Cache hit for {record_config.record_type.value}Record")
            return cls._cache[cache_key]

        cls._cache_stats["misses"] += 1
        log.debug(
            f"Cache miss for {record_config.record_type.value}Record, creating new class"
        )
        record_class = factory_func(record_config)
        cls._cache[cache_key] = record_class
        return record_class

    @classmethod
    def get_cache_key(cls, record_config: RecordConfig) -> str:
        """
        Generate a unique cache key for the record configuration.
        The key is formed by concatenating the `record_type` with the
        `name`, `type` and `ASTM position` of each field.
        """
        import hashlib

        record_type = f"{record_config.record_type.value}:"
        for field in record_config.fields:
            record_type += (
                f"{field.field_name}:{field.field_type}:{field.astm_position}:"
            )
        return hashlib.md5(record_type.encode()).hexdigest()

    @classmethod
    def clear_cache(cls):
        """Clear the cache."""
        cls._cache.clear()
        cls._cache_stats = {"hits": 0, "misses": 0}
        log.info(f"Cache cleared successfully. Cache stats:{cls._cache_stats}")

    @classmethod
    def get_cache_stats(cls) -> Dict[str, int]:
        """Get cache statistics."""
        return cls._cache_stats.copy()

"""
Cache utilities for managing scenario summary cache invalidation.

This module provides functions to invalidate cached summary responses
when scenario data is updated.
"""

import logging
from typing import List

from django.conf import settings
from django.core.cache import cache
from django.db import connection

logger = logging.getLogger(__name__)


def get_scenario_summary_cache_keys(scenario_id: int) -> List[str]:
    """
    Get all cache keys for summary queries of a given scenario.

    This uses a workaround since Django's database cache backend
    doesn't support pattern-based deletion.

    The approach queries the cache table directly for all keys matching
    the pattern 'summaries:{scenario_id}:*'

    Args:
        scenario_id: The scenario ID to find cache keys for

    Returns:
        List of cache keys that match the scenario's summary pattern
    """
    cache_location = settings.CACHES["default"]["LOCATION"]
    prefix = f"summaries:{scenario_id}:"

    try:
        # Query the cache table directly for matching keys
        # The key column in Django's database cache is typically 'cache_key'
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT cache_key FROM {cache_location}
                WHERE cache_key LIKE %s
                """,
                [f"{prefix}%"],
            )
            rows = cursor.fetchall()
            return [row[0] for row in rows]
    except Exception as e:
        logger.warning(
            f"Failed to query cache keys for scenario {scenario_id}: {e}. "
            "Falling back to blind deletion."
        )
        # If direct query fails, return empty list
        # The calling function will use cache.clear() as fallback
        return []


def invalidate_scenario_summary_cache(scenario_id: int) -> int:
    """
    Invalidate all cached summary responses for a specific scenario.

    This clears all cache entries matching the pattern 'summaries:{scenario_id}:*',
    forcing fresh computation on the next request.

    Args:
        scenario_id: The scenario ID for which to invalidate cache

    Returns:
        Number of cache entries deleted
    """
    cache_keys = get_scenario_summary_cache_keys(scenario_id)

    deleted_count = len(cache_keys)
    cache.delete_many(cache_keys)

    if deleted_count > 0:
        logger.info(
            f"Invalidated {deleted_count} summary cache entries for scenario {scenario_id}"
        )
    else:
        logger.debug(f"No cache entries found to invalidate for scenario {scenario_id}")

    return deleted_count

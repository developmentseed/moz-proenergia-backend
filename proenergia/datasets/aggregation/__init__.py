"""
Aggregation module for efficient field summary computations.

This module provides optimized strategies for computing field summaries
with various combinations of filters and grouping.
"""

from .aggregators import (
    SimpleAggregator,
    FilteredAggregator,
    SingleGroupAggregator,
    MultiGroupAggregator,
    get_aggregator,
)
from .filters import FilterParser
from .query_builder import SummaryQueryBuilder

__all__ = [
    "SimpleAggregator",
    "FilteredAggregator",
    "SingleGroupAggregator",
    "MultiGroupAggregator",
    "get_aggregator",
    "FilterParser",
    "SummaryQueryBuilder",
]

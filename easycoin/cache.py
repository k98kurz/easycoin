"""
Segmented LRU (Least Recently Used) cache implementation for managing distinct
receive and send cache segments. Provides named cache instances with automatic
eviction when capacity limits are reached. Each cache segment tracks access order
independently to evict the least recently used items first, with a registry
preventing duplicate instances of the same named segment.
"""

from __future__ import annotations
from collections import OrderedDict
from enum import Enum
from random import choice as random_choice
from time import time
from typing import Any, Hashable


_caches: dict[tuple[str, CacheKind], LRUCache] = {}


class CacheKind(Enum):
    """Enum specifying the cache type: RECEIVE or SEND."""
    RECEIVE = 'recv'
    SEND = 'send'


class LRUCache:
    def __init__(self, name: str, kind: CacheKind, limit: int = 1000):
        if (name, kind) in _caches:
            raise ValueError('cannot instantiate the same LRUCache twice')
        self.name = name
        self.kind = kind
        self.od = OrderedDict()
        self.limit = int(limit)
        _caches[(name, kind)] = self

    def keys(self) -> list:
        """Returns a list of cache keys in order from most recently
            used to least. Does not affect LRU order.
        """
        l = list(self.od.keys())
        l.reverse()
        return l

    def get(self, key: Hashable) -> Any | None:
        """If the key exists in the cache, mark it as most recently used
            and return it.
        """
        if key not in self.od:
            return None
        # Move to end (most recently used)
        self.od.move_to_end(key)
        return self.od[key]

    def peak(self, key: Hashable) -> Any | None:
        """If the key exists in the cache, return it without updating
            LRU order.
        """
        return self.od.get(key, None)

    def put(self, key: Hashable, value: Any) -> None:
        """Put the value in the cache at the key. If the cache growth
            hits its limit, evict the least recently used cache item.
        """
        if key in self.od:
            self.od.move_to_end(key)
        self.od[key] = value
        if len(self.od) > self.limit:
            # Pop the oldest (first item)
            self.od.popitem(last=False)

    def pop(self, key: Hashable) -> Any | None:
        """If the key exists in the cache, remove and return it."""
        if key in self.od:
            return self.od.pop(key)

    def peak_last(self) -> tuple[Hashable, Any] | None:
        """Peak at the last (LRU) item in the cache. Does not affect ordering."""
        keys = list(self.od.keys())
        if keys:
            return (keys[-1], self.peak(keys[-1]))

    def peak_random(self) -> tuple[Hashable, Any] | None:
        """Peak at a random item in the cache. Does not affect LRU order."""
        keys = self.keys()
        if keys:
            k = random_choice(keys)
            return (k, self.peak(k))

    def clear(self) -> None:
        """Clears the cache."""
        self.od.clear()

    @classmethod
    def get_instance(cls, name: str, kind: CacheKind, limit: int = 1000) -> LRUCache:
        """Get a named LRUCache instance. If it does not yet exist,
            instantiate it.
        """
        if (name, kind) in _caches:
            return _caches[(name, kind)]
        return cls(name, kind, limit)


class TimeoutCache:
    def __init__(self, limit: int = 1000, timeout: float = 60.0):
        self.od: OrderedDict[Hashable, tuple[Any, float]] = OrderedDict()
        self.limit = int(limit)
        self.timeout = timeout

    def _expire(self) -> None:
        """Remove expired items from the cache. Items are ordered by
            insertion timestamp, so we only need to iterate until we find
            the first unexpired item.
        """
        current_time = time()
        for key in list(self.od.keys()):
            value, timestamp = self.od[key]
            if current_time - timestamp > self.timeout:
                del self.od[key]
            else:
                break

    def keys(self) -> list:
        """Returns a list of cache keys in order from most recently
            used to least. Does not affect LRU order.
        """
        self._expire()
        l = list(self.od.keys())
        l.reverse()
        return l

    def get(self, key: Hashable) -> Any | None:
        """If the key exists in the cache, mark it as most recently used
            and return it.
        """
        self._expire()
        if key not in self.od:
            return None
        self.od.move_to_end(key)
        return self.od[key][0]

    def peak(self, key: Hashable) -> Any | None:
        """If the key exists in the cache, return it without updating
            LRU order or expiring items.
        """
        if key not in self.od:
            return None
        return self.od[key][0]

    def put(self, key: Hashable, value: Any) -> None:
        """Put the value in the cache at the key. If the cache growth
            hits its limit, evict the least recently used cache item.
        """
        self._expire()
        if key in self.od:
            self.od.move_to_end(key)
        self.od[key] = (value, time())
        if len(self.od) > self.limit:
            self.od.popitem(last=False)

    def pop(self, key: Hashable) -> Any | None:
        """If the key exists in the cache, remove and return it."""
        if key in self.od:
            value, _ = self.od.pop(key)
            return value

    def clear(self) -> None:
        """Clears the cache."""
        self.od.clear()


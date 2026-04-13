# easycoin.cache

## Classes

### `CacheKind(Enum)`

### `LRUCache`

#### Methods

##### `__init__(name: str, kind: CacheKind, limit: int = 1000):`

##### `get(key: Hashable) -> Any | None:`

If the key exists in the cache, mark it as most recently used and return it.

##### `peak(key: Hashable) -> Any | None:`

If the key exists in the cache, return it without updating LRU order.

##### `put(key: Hashable, value: Any) -> None:`

Put the value in the cache at the key. If the cache growth hits its limit, evict
the least recently used cache item.

##### `pop(key: Hashable) -> Any | None:`

If the key exists in the cache, remove and return it.

##### `clear() -> None:`

Clears the cache.

##### `@classmethod get_instance(name: str, kind: CacheKind, limit: int = 1000) -> LRUCache:`

Get a named LRUCache instance. If it does not yet exist, instantiate it.



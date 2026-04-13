# easycoin.state

StateManager: subscribe/publish + state bag for cross-screen updates.

## Classes

### `LogEntry`

Single log entry in event log.

#### Annotations

- message: <class 'str'>
- level: <class 'str'>
- timestamp: <class 'datetime.datetime'>

#### Methods

##### `__init__(message: str, level: str, timestamp: datetime):`

### `StateManager`

Pub/sub layer with some state sharing features.

#### Methods

##### `__init__(logger: Logger):`

Initialize StateManager with logger.

##### `subscribe(event_name: str, listener: Callable):`

Subscribe to a specific event.

##### `unsubscribe(event_name: str, listener: Callable):`

Unsubscribe from a specific event. Silently ignores if not subscribed.

##### `publish(event_name: str, data: Any = None):`

Publish an event to all subscriptions to that event.

##### `get(key: str) -> typing.Any | None:`

Get some state.

##### `set(key: str, data: Any):`

Set some state. Notify subscriptions for the `set_{key}` event.

##### `unset(key: str):`

Unset some state. Notify subscriptions for the `unset_{key}` event.

##### `append(key: str, data: Any):`

Append to a list. If the list does not yet exist, create it. Notify
subscriptions for the `append_{key}` event. Raises `TypeError` if the state with
that key is set to a non-list.

##### `remove(key: str, data: Any):`

Remove from a list. If the list does not yet exist, return. Notify subscriptions
for the `remove_{key}` event. Raises `TypeError` if the state with that key is
set to a non-list.

##### `add_log_entry(message: str, level: str):`

Add a log entry to state and push to subscriptions.

## Values

- `get_state_manager`: _lru_cache_wrapper


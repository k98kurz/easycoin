# easycoin.config

Configuration management for the easycoin application. Provides validated
configuration settings with an event-driven pub/sub system for reacting to
configuration changes.

## Classes

### `ConfigManager`

Manages application configuration with validation and change notifications.

#### Methods

##### `__init__(app_name: str = 'easycoin'):`

Initialize the configuration manager for the specified application.

##### `subscribe(event_name: str, listener: Callable):`

Subscribe to a specific event.

##### `unsubscribe(event_name: str, listener: Callable):`

Unsubscribe from a specific event. Silently ignores if not subscribed.

##### `publish(event_name: str, data: Any = None):`

Publish an event to all subscriptions to that event.

##### `load():`

Load configuration from disk, updating in-memory state.

##### `save():`

Persist current configuration to disk.

##### `path(file_or_subdir: str | list[str] | None = None) -> str:`

Return the full path to a file or subdirectory in the app config dir.

##### `get(key: str = None) -> list | bool | str | int | float | None:`

Retrieve a configuration value, applying schema transformations.

##### `set(key: str, value: list | bool | str | int | float) -> ValueError | None:`

Update a configuration value, validating against schema and notifying.

##### `unset(key: str):`

Remove a configuration value and notify subscribers.

##### `get_db_path() -> str:`

Return the full path to the application database file.

##### `get_log_path() -> str:`

Return the full path to the application log file.

## Values

- `DEFAULT_PORT`: int
- `get_config_manager`: _lru_cache_wrapper


# easycoin.cryptoworker

## Classes

### `JobType(Enum)`

Enum specifying the job type: VALIDATE_TXN or MINE_COINS.

#### Methods

##### `pack() -> bytes:`

Serialize to bytes.

##### `@classmethod unpack(data: bytes) -> JobType:`

Deserialize from bytes.

### `JobMessage`

Object for communicating jobs and results via queues.

#### Annotations

- job_type: JobType
- job_data: bytes
- debug: str | bool
- result: bool | list[Coin | Exception] | Exception | None
- queue: deque

#### Methods

##### `__init__(job_type: JobType, job_data: bytes = b'', debug: str | bool = False, result: bool | list[Coin | Exception] | Exception | None = None, queue: deque = None):`

##### `pack() -> bytes:`

Serialize to bytes.

##### `@classmethod unpack(data: bytes, inject: dict = {}) -> JobMessage:`

Deserialize from bytes.

## Functions

### `set_mining_pool_size(max_workers: int):`

### `submit_txn_job(txn: Txn, output_q: deque | None = None, debug: str | bool = False):`

Queues a job to validate the given `Txn`. If `output_q` is provided, the result
will be appended to that queue. `Txn` validation jobs will be completed in
batches of up to 16 at a time, but the results will be placed individually onto
the result queue. (Without `output_q`, use `get_txn_job_result()` to retrieve
ready results from completed txn validation jobs.)

### `get_txn_job_result() -> JobMessage | None:`

If a txn validation job has completed, return the `JobMessage` with the original
job data and the result. Otherwise, return `None`.

### `submit_mine_job(lock: bytes | Script, total_amount: int, number_of_coins: int, net_id: str | None = None, net_state: bytes | None = None, output_q: deque | None = None):`

Queues a mining job to mine `total_amount` of EC⁻¹ across `number_of_coins`
Coins. If `output_q` is specified, the result of the mining job (with
`JobMessage.result: list[Coin]`) will be appended to that queue. Coins will be
locked with the given `lock`.

### `get_mined_coins() -> list[Coin | Exception] | None:`

If a mining job has completed, return the newly mined `Coin`s or the
`Exception`s encountered during mining. Otherwise, return `None`.

### `async work():`

Continually work mining and Txn validation jobs.

### `async work_txn_validation_jobs() -> list[JobMessage] | None:`

Works a batch of up to 16 available Txn validation jobs, then returns a
`list[JobMessage]` each with the original job data and the validation result.

### `async work_mine_job() -> tuple[JobMessage, list[Coin]] | None:`

Works a mining job if one is available, then returns the original `JobMessage`
and the list of new Coins that were mined; or it returns `None` if a job was not
available.



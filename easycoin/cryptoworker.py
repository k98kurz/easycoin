from __future__ import annotations
from .models import Txn, Coin
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from tapescript import Script
import asyncio
import packify


_validate_txn_jobs: deque[JobMessage] = deque([], 100)
_validate_txn_results: deque[JobMessage] = deque([], 100)
_mine_coins_jobs: deque[JobMessage] = deque([], 100)
_mine_coins_results: deque[JobMessage] = deque([], 100)
_mining_pool = ProcessPoolExecutor(max_workers=4)
_txn_validation_pool = ProcessPoolExecutor(max_workers=4)

def set_mining_pool_size(max_workers: int):
    _mining_pool._max_workers = int(max_workers)
    #global _mining_pool
    #_mining_pool = ProcessPoolExecutor(max_workers=int(max_workers))


class JobType(Enum):
    """Enum specifying the job type: VALIDATE_TXN or MINE_COINS."""
    VALIDATE_TXN = 0
    MINE_COINS = 1

    def pack(self) -> bytes:
        """Serialize to bytes."""
        return self.value.to_bytes(1, 'big')

    @classmethod
    def unpack(cls, data: bytes) -> JobType:
        """Deserialize from bytes."""
        return cls(int.from_bytes(data, 'big'))


@dataclass
class JobMessage:
    """Object for communicating jobs and results via queues."""
    job_type: JobType = field()
    job_data: bytes = field(default=b'')
    debug: str|bool = field(default=False)
    result: bool|list[Coin|Exception]|Exception|None = field(default=None)
    queue: deque = field(default=None)

    def pack(self) -> bytes:
        """Serialize to bytes."""
        return packify.pack([self.job_type, self.job_data, self.result])

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> JobMessage:
        """Deserialize from bytes."""
        return cls(*packify.unpack(data, inject=inject))


# communication with the worker
def submit_txn_job(txn: Txn, output_q: deque|None = None, debug: str|bool = False):
    """Queues a job to validate the given `Txn`. If `output_q` is
        provided, the result will be appended to that queue. `Txn`
        validation jobs will be completed in batches of up to 16 at a
        time, but the results will be placed individually onto the
        result queue. (Without `output_q`, use `get_txn_job_result()` to
        retrieve ready results from completed txn validation jobs.)
    """
    jm = JobMessage(JobType.VALIDATE_TXN, txn.pack(), debug)
    if output_q:
        jm.queue = output_q
    _validate_txn_jobs.append(jm)

def get_txn_job_result() -> JobMessage|None:
    """If a txn validation job has completed, return the `JobMessage`
        with the original job data and the result. Otherwise, return
        `None`.
    """
    try:
        if len(_validate_txn_results):
            return _validate_txn_results.popleft()
    except IndexError:
        pass

def submit_mine_job(
        lock: bytes|Script, total_amount: int, number_of_coins: int,
        net_id: int|None = None, net_state: bytes|None = None,
        output_q: deque|None = None
    ):
    """Queues a mining job to mine `total_amount` of EC⁻¹ across
        `number_of_coins` Coins. If `output_q` is specified, the result
        of the mining job (with `JobMessage.result: list[Coin]`) will be
        appended to that queue. Coins will be locked with the given
        `lock`.
    """
    lock = lock.bytes if type(lock) is Script else lock
    jm = JobMessage(JobType.MINE_COINS, packify.pack([
        lock, total_amount, number_of_coins, net_id, net_state
    ]))
    if output_q:
        jm.queue = output_q
    _mine_coins_jobs.append(jm)

def get_mined_coins() -> list[Coin|Exception]|None:
    """If a mining job has completed, return the newly mined `Coin`s or
        the `Exception`s encountered during mining. Otherwise, return
        `None`.
    """
    try:
        if len(_mine_coins_results):
            jm: JobMessage = _mine_coins_results.popleft()
            return jm.result
    except IndexError:
        pass


# the actual worker logic
async def work():
    """Continually work mining and Txn validation jobs."""
    while True:
        await asyncio.sleep(0.1)
        await _work_txn_validation_jobs()
        await _work_mine_job()

def _validate(jm: JobMessage) -> tuple[JobMessage, bool]:
    try:
        return (jm, Txn.unpack(jm.job_data).validate(debug=jm.debug, reload=False))
    except Exception as e:
        return (jm, e)

async def work_txn_validation_jobs() -> list[JobMessage]|None:
    """Works a batch of up to 16 available Txn validation jobs, then
        returns a `list[JobMessage]` each with the original job data and
        the validation result.
    """
    # process up to 16 Txns in a batch
    jobs = []
    while len(_validate_txn_jobs) > 0 and len(jobs) < 16:
        try:
            jobs.append(_validate_txn_jobs.popleft())
        except IndexError:
            pass

    if len(jobs) == 0:
        return None

    # execute in pool
    loop = asyncio.get_running_loop()
    tasks = [
        loop.run_in_executor(
            _txn_validation_pool, 
            _validate,
            j,
        )
        for j in jobs
    ]
    result = await asyncio.gather(*tasks)

    # set each job message's result
    jobs = []
    for jm, res in result:
        jm.result = res
        jobs.append(jm)
    return jobs

async def _work_txn_validation_jobs():
    # work the jobs
    result = await work_txn_validation_jobs()
    if result is None:
        return

    # push results to a queue
    for jm in result:
        if jm.queue:
            jm.queue.append(jm)
        else:
            _validate_txn_results.append(jm)

def __mine(j: tuple):
    try:
        return Coin.mine(*j).pack()
    except Exception as e:
        return e

async def work_mine_job() -> tuple[JobMessage, list[Coin]]|None:
    """Works a mining job if one is available, then returns the original
        `JobMessage` and the list of new Coins that were mined; or it
        returns `None` if a job was not available.
    """
    try:
        if len(_mine_coins_jobs):
            # get and parse a job message
            jm: JobMessage = _mine_coins_jobs.popleft()
            data = packify.unpack(jm.job_data)
            lock, total_amount, number_of_coins, net_id, net_state = data

            # calculate job values
            amt_per_coin = total_amount // number_of_coins
            amt_per_coin += 1 if total_amount % number_of_coins else 0
            jobs = [
                (lock, amt_per_coin, net_id, net_state, i*1_000_000)
                for i in range(number_of_coins)
            ]

            # execute in pool
            loop = asyncio.get_running_loop()
            tasks = [
                loop.run_in_executor(_mining_pool, __mine, j)
                for j in jobs
            ]
            result = await asyncio.gather(*tasks)
            result = [
                Coin.unpack(r) if type(r) is bytes else r
                for r in result
            ]
            return (jm, result)
    except IndexError:
        pass

async def _work_mine_job():
    result = await work_mine_job()
    if not result:
        return
    # push results to a queue
    jm, coins = result
    jm.result = coins
    if jm.queue:
        jm.queue.append(jm)
    else:
        _mine_coins_results.append(jm)



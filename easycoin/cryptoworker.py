from __future__ import annotations
from .models import Txn, Coin
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from tapescript import Script
import asyncio
import packify


_validate_txn_jobs = deque([], 100)
_validate_txn_results = deque([], 100)
_mine_coins_jobs = deque([], 100)
_mine_coins_results = deque([], 100)
_mining_pool = ProcessPoolExecutor(max_workers=4)
_txn_validation_pool = ProcessPoolExecutor(max_workers=4)


class JobType(Enum):
    VALIDATE_TXN = 0
    MINE_COINS = 1

    def pack(self) -> bytes:
        return self.value.to_bytes(1, 'big')

    @classmethod
    def unpack(cls, data: bytes) -> JobType:
        return cls(int.from_bytes(data, 'big'))


@dataclass
class JobMessage:
    job_type: JobType = field()
    job_data: bytes = field(default=b'')
    result: bool|bytes|int|None = field(default=None)
    queue: deque = field(default=None)

    def pack(self) -> bytes:
        return packify.pack([self.job_type, self.job_data, self.result])

    @classmethod
    def unpack(cls, data: bytes, inject: dict = {}) -> JobMessage:
        return cls(*packify.unpack(data, inject=inject))


# communication with the worker
def submit_txn_job(txn: Txn, output_q: deque|None = None):
    jm = JobMessage(JobType.VALIDATE_TXN, txn.pack())
    if output_q:
        jm.queue = output_q
    _validate_txn_jobs.append(jm)

def get_txn_job_result() -> JobMessage|None:
    try:
        if not len(_validate_txn_results):
            return None
        return _validate_txn_results.popleft()
    except IndexError:
        return None

def submit_mine_job(
    lock: bytes|Script, total_amount: int, number_of_coins: int,
    output_q: deque|None = None
):
    lock = lock.bytes if type(lock) is Script else lock
    jm = JobMessage(JobType.MINE_COINS, packify.pack([lock, total_amount, number_of_coins]))
    if output_q:
        jm.queue = output_q
    _mine_coins_jobs.append(jm)

def get_mined_coin() -> Coin|None:
    try:
        if not len(_mine_coins_results):
            return None
        jm: JobMessage = _mine_coins_results.popleft()
        return Coin.unpack(jm.job_data)
    except IndexError:
        return None


# the actual worker logic
async def work():
    """Continually work mining and Txn validation jobs."""
    while True:
        await _work_txn_validation_jobs()
        await _work_mine_job()

def _validate(jm: JobMessage) -> tuple[JobMessage, bool]:
    return (jm, Txn.unpack(jm.job_data).validate())

async def work_txn_validation_jobs() -> list[JobMessage]|None:
    """Works a batch of up to 16 available Txn validation jobs, then
        returns a list of 
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
    return Coin.mine(*j).pack()

async def work_mine_job() -> tuple[JobMessage, list[Coin]]|None:
    """Works a mining job if one is available, then returns the job
        message and the list of new Coins that were mined; or it returns
        None if a job was not available.
    """
    try:
        if len(_mine_coins_jobs):
            # get and parse a job message
            jm: JobMessage = _mine_coins_jobs.popleft()
            lock, total_amount, number_of_coins = packify.unpack(jm.job_data)

            # calculate job values
            amt_per_coin = total_amount // number_of_coins
            amt_per_coin += 1 if total_amount % number_of_coins else 0
            jobs = [
                (lock, amt_per_coin, None, i*1_000_000)
                for i in range(number_of_coins)
            ]

            # execute in pool
            loop = asyncio.get_running_loop()
            tasks = [
                loop.run_in_executor(_mining_pool, __mine, j)
                for j in jobs
            ]
            result = await asyncio.gather(*tasks)
            return (jm, [Coin.unpack(r) for r in result])
    except IndexError:
        return None

async def _work_mine_job():
    result = await work_mine_job()
    if result:
        jm, coins = result 
    # push results to a queue
    if jm.queue:
        [jm.queue.append(c) for c in coins]
    else:
        [_mine_coins_results.append(c) for c in coins]



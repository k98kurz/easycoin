from time import time, perf_counter
from typing import Callable


_lambda_id = lambda x: x
_lambda_add = lambda x: x+x
_lambda_mult = lambda x: x*x
_lambda_div = lambda x: 1/x
_lambda_sum = lambda x: sum(x)
_lambda_dict = lambda x, y: x[y]
_lambda_pc = lambda: -(perf_counter() - perf_counter())
_lambda_tm = lambda: -(time() - time())


def _callstack_switch(x):
    return x

def _branch(x):
    if x:
        return x
    return 0

def timeit(func: Callable, args: list = []) -> int:
    start = perf_counter()
    func(*args)
    end = perf_counter()
    return end - start

def benchmark(count: int, func: Callable, args: list = []) -> list[int]:
    return [timeit(func, args) for _ in range(count)]

def microbench() -> dict:
    """Run the microbenchmark suite."""
    res = {
        'lambda': sum(benchmark(30, _lambda_id, [1]))/30,
        'add': sum(benchmark(30, _lambda_add, [1.0]))/30,
        'mult': sum(benchmark(30, _lambda_mult, [1.0]))/30,
        'div': sum(benchmark(30, _lambda_div, [1.0]))/30,
        'sum': sum(benchmark(30, _lambda_sum, [[i/1.0 for i in range(30)]]))/30,
        'dict': sum(benchmark(30, _lambda_dict, [{1:1}, 1]))/30,
        'pc': sum([_lambda_pc() for _ in range(30)])/30,
        'tm': sum([_lambda_tm() for _ in range(30)])/30,
        'call': sum(benchmark(30, _callstack_switch, [1]))/30,
        'if': (sum(benchmark(15, _branch, [0])) + sum(benchmark(15, _branch, [1])))/30,
    }
    res['add'] -= res['lambda']
    res['mult'] -= res['lambda']
    res['div'] -= res['lambda']
    res['dict'] -= res['lambda']
    res['offset'] = 30 * (
        res['lambda'] + res['add'] * 5 + res['mult'] + res['div'] + res['sum'] +
        res['dict'] + res['pc'] + res['tm'] + res['call'] * 31 + res['if']
    ) + res['add'] * 18 + res['mult'] * 6 + res['div'] * 9 + res['call'] + \
    res['dict'] * 24
    return res

def calc_microbench_offset(ops: dict = {}) -> float:
    """Calculate a time offset using a microbenchmark."""
    bench = microbench()
    overhead = bench['add'] * 2 + bench['mult'] + bench['dict'] * 4
    if 'lambda' in ops:
        bench['offset'] += bench['lambda'] * ops['lambda'] + overhead
    if 'add' in ops:
        bench['offset'] += bench['add'] * ops['add'] + overhead
    if 'mult' in ops:
        bench['offset'] += bench['mult'] * ops['mult'] + overhead
    if 'div' in ops:
        bench['offset'] += bench['div'] * ops['div'] + overhead
    if 'sum' in ops:
        bench['offset'] += bench['sum'] * ops['sum'] + overhead
    if 'dict' in ops:
        bench['offset'] += bench['dict'] * ops['dict'] + overhead
    if 'pc' in ops:
        bench['offset'] += bench['pc'] * ops['pc'] + overhead
    if 'tm' in ops:
        bench['offset'] += bench['tm'] * ops['tm'] + overhead
    if 'call' in ops:
        bench['offset'] += bench['call'] * ops['call'] + overhead
    if 'if' in ops:
        bench['offset'] += bench['if'] * ops['if'] + overhead
    return bench['offset'] + bench['if'] * 10 + bench['add'] * 7 + \
        bench['mult'] * 6 + bench['dict'] * 9 + bench['call']


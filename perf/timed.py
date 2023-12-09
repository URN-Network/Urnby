import logging
import time

def perf(func):
    def wrapper():
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        logging.info(f'{func.__module__}.{func.__name__} took {end-start}s')
    return wrapper
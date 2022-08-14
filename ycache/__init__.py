__version__ = '0.1.0'

import hashlib
import pickle
import time
from functools import lru_cache, wraps

from diskcache import Cache
from loguru import logger


def pickled_lru_cache(maxsize=128, typed=False, ttl=10):
    PICKLE_PROTOCOL: int = pickle.HIGHEST_PROTOCOL

    class Result:
        __slots__ = ('value', 'death')

        def __init__(self, value, death):
            self.value = value
            self.death = death

    def _decorator(func):
        @lru_cache(maxsize=maxsize, typed=typed)
        def cached_func_with_ttl(pickled_args, pickled_kwargs) -> Result:
            args = pickle.loads(pickled_args)
            kwargs = pickle.loads(pickled_kwargs)

            value = func(*args, **kwargs)
            death = time.monotonic() + ttl
            return Result(value=value, death=death)

        @wraps(func)
        def _wrapper(*args, **kwargs):
            pickled_args = pickle.dumps(args, PICKLE_PROTOCOL)
            pickled_kwargs = pickle.dumps(kwargs, PICKLE_PROTOCOL)
            result: Result = cached_func_with_ttl(pickled_args, pickled_kwargs)

            if result.death < time.monotonic():  # 如果已超时
                logger.debug(
                    f'before expired: {cached_func_with_ttl.cache_info()}')
                cached_func_with_ttl.cache_clear()
                result.value = func(*args, **kwargs)  # 重新计算
                result.death = time.monotonic() + ttl

            return result.value

        _wrapper.cache_info = cached_func_with_ttl.cache_info
        _wrapper.cache_clear = cached_func_with_ttl.cache_clear

        return _wrapper

    return _decorator


def disk_cache(cache_dir='.temp', ttl=60*60*24):
    def _decorator(func):
        PICKLE_PROTOCOL: int = pickle.HIGHEST_PROTOCOL

        def md5(s) -> str:
            m = hashlib.md5()
            m.update(str(s).encode('utf-8'))
            return m.hexdigest()

        def _make_key(namespace, *args, **kwargs):
            pickled_args: bytes = pickle.dumps(args, PICKLE_PROTOCOL)
            pickled_kwargs: bytes = pickle.dumps(kwargs, PICKLE_PROTOCOL)
            key: str = f'{namespace}-{pickled_args}-{pickled_kwargs}'
            return md5(key)

        @wraps(func)
        def _wrapper(*args, **kwargs):
            key: str = _make_key(func.__name__, args, kwargs)
            with Cache(cache_dir) as cache:
                if not cache.get(key):
                    logger.debug(f'not hitted, recache key:[{key}]')
                    result = func(*args, **kwargs)
                    cache.set(key, pickle.dumps(result), expire=ttl)
                    return result
                else:
                    logger.debug(f'[{key}] hitted in cache')
                    return pickle.loads(cache.get(key))
        return _wrapper
    return _decorator

from loguru import logger
from dis import code_info
import functools
import time
from ycache import pickled_lru_cache
import json

logger.add('output/log/test_pickle_lru_cache_{time}.log', retention=1)


class TestPickleLruCache:
    def test_functional_cache(self):
        @pickled_lru_cache()
        def function_that_takes_long(*args, **kwargs):
            res = json.dumps({"args": args, "kwargs": kwargs})
            return res

        function_that_takes_long(
            1, 3, [2, 3], {2: 3}, a=2, b=3, c=[2, 3], d={2: 3})

        c_info = function_that_takes_long.cache_info()
        logger.debug(c_info)

        assert c_info == functools._CacheInfo(
            hits=0, misses=1, maxsize=128, currsize=1)

        # try again, it should be hitted in cache
        function_that_takes_long(
            1, 3, [2, 3], {2: 3}, a=2, b=3, c=[2, 3], d={2: 3})

        c_info = function_that_takes_long.cache_info()
        assert c_info == functools._CacheInfo(
            hits=1, misses=1, maxsize=128, currsize=1)

    def test_with_ttl(self):
        @pickled_lru_cache(ttl=1)
        def function_that_takes_long(*args, **kwargs):
            res = json.dumps({"args": args, "kwargs": kwargs})
            return res

        # 模拟1秒内缓存尚未过期
        for i in range(2):
            time.sleep(0.5)
            function_that_takes_long(
                2, 3, [2, 3], {2: 3}, a=2, b=3, c=[2, 3], d={2: 3})

        c_info = function_that_takes_long.cache_info()
        print(c_info)
        assert c_info == functools._CacheInfo(
            hits=1, misses=1, maxsize=128, currsize=1)

        # 模拟超过1秒后缓存尚过期
        for i in range(3):
            time.sleep(0.4)
            function_that_takes_long(
                2, 3, [2, 3], {2: 3}, a=2, b=3, c=[2, 3], d={2: 3})

        c_info = function_that_takes_long.cache_info()
        assert c_info == functools._CacheInfo(
            hits=0, misses=1, maxsize=128, currsize=1)

    def test_diff_args(self):
        @pickled_lru_cache()
        def function_that_takes_long(*args, **kwargs):
            res = json.dumps({"args": args, "kwargs": kwargs})
            return res

        function_that_takes_long(
            1, 3, [2, 3], {2: 3}, a=2, b=3, c=[2, 3], d={2: 3})

        function_that_takes_long(
            2, 3, [2, 5], {2: 5}, a=2, b=3, c=[2, 3], d={2: 3})

        c_info = function_that_takes_long.cache_info()
        assert c_info == functools._CacheInfo(
            hits=0, misses=2, maxsize=128, currsize=2)

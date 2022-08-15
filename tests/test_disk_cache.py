import json
from ycache import disk_cache
from loguru import logger

logger.add('output/log/test_disk_cache_{time}.log', retention=1)


class TestDiskCache:

    def test_functional_disk_cache(self):
        @ disk_cache()
        def function_that_takes_long(*args, **kwargs):
            res = json.dumps({"args": args, "kwargs": kwargs})
            return res

        result = function_that_takes_long(
            1, 3, [2, 3], {2: 3}, a=2, b=3, c=[2, 3], d={2: 3})

        expected = '{"args": [1, 3, [2, 3], {"2": 3}], "kwargs": {"a": 2, "b": 3, "c": [2, 3], "d": {"2": 3}}}'

        assert result == expected

        cached_result = function_that_takes_long(
            1, 3, [2, 3], {2: 3}, a=2, b=3, c=[2, 3], d={2: 3})

        assert cached_result == expected

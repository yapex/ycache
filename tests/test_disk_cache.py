import json

import pandas as pd
from loguru import logger
from ycache import disk_cache

logger.add('output/log/test_disk_cache_{time}.log', retention=1)


class TestDiskCache:

    def test_functional_disk_cache(self):
        @ disk_cache()
        def function_that_takes_long(*args, **kwargs):
            res = json.dumps({"args": args, "kwargs": kwargs})
            return res

        result = function_that_takes_long(
            1, 3, [2, 3], {2: 3}, a=2, b=3, c=[2, 3], d={2: 3})

        expected = (
            '{"args": [1, 3, [2, 3], {"2": 3}], '
            '"kwargs": {"a": 2, "b": 3, "c": [2, 3], "d": {"2": 3}}}')

        assert result == expected

        cached_result = function_that_takes_long(
            1, 3, [2, 3], {2: 3}, a=2, b=3, c=[2, 3], d={2: 3})

        assert cached_result == expected

    def test_cache_dataframe(self):
        @disk_cache()
        def get_df(name):
            download_url = (
                "https://raw.githubusercontent.com/fivethirtyeight/"
                "data/master/college-majors/recent-grads.csv"
            )
            df = pd.read_csv(download_url)
            return df

        result_df = get_df('recent-grads')
        assert len(result_df) > 0

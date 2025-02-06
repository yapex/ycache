import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import pytest
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

    def test_ttl_expiration(self):
        """测试缓存 TTL 过期机制"""
        @disk_cache(ttl=1)  # 设置 1 秒过期
        def get_timestamp():
            return time.time()

        # 第一次调用
        first_result = get_timestamp()
        # 立即再次调用，应该返回缓存的结果
        cached_result = get_timestamp()
        assert first_result == cached_result

        # 等待缓存过期
        time.sleep(1.1)
        # 再次调用，应该获得新的结果
        new_result = get_timestamp()
        assert new_result != first_result

    def test_different_argument_types(self):
        """测试不同类型参数的缓存效果"""
        @disk_cache()
        def process_different_types(arg):
            return f"processed_{arg}"

        # 测试不同类型的参数
        cases = [
            42,  # 整数
            "string",  # 字符串
            3.14,  # 浮点数
            [1, 2, 3],  # 列表
            {"a": 1},  # 字典
            (1, 2),  # 元组
            True,  # 布尔值
        ]

        for case in cases:
            first_call = process_different_types(case)
            second_call = process_different_types(case)
            assert first_call == second_call
            assert first_call == f"processed_{case}"

    def test_exception_handling(self):
        """测试异常情况下的缓存行为"""
        @disk_cache()
        def failing_function(should_fail=True):
            if should_fail:
                raise ValueError("Intended error")
            return "success"

        # 测试异常是否正常抛出
        with pytest.raises(ValueError):
            failing_function(True)

        # 测试正常情况
        assert failing_function(False) == "success"
        # 再次调用确认缓存生效
        assert failing_function(False) == "success"

    def test_concurrent_access(self):
        """测试并发访问情况下的缓存表现"""
        @disk_cache()
        def slow_function(x):
            time.sleep(0.1)  # 模拟耗时操作
            return x * 2

        def worker(x):
            return slow_function(x)

        # 创建多个并发任务
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(worker, i) for i in range(5)]
            results = [f.result() for f in as_completed(futures)]

        # 验证结果
        assert sorted(results) == [0, 2, 4, 6, 8]

    def test_large_data_caching(self):
        """测试大数据量缓存"""
        @disk_cache()
        def generate_large_data(size):
            return "x" * size

        # 测试 1MB 数据
        data_size = 1024 * 1024
        large_data = generate_large_data(data_size)
        assert len(large_data) == data_size

        # 验证缓存是否正常工作
        cached_data = generate_large_data(data_size)
        assert len(cached_data) == data_size
        assert cached_data == large_data

    def test_custom_cache_dir(self):
        """测试自定义缓存目录"""
        import tempfile
        import os

        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            @disk_cache(cache_dir=temp_dir)
            def simple_function(x):
                return x * 2

            # 执行函数并验证结果
            result = simple_function(21)
            assert result == 42

            # 验证缓存目录是否被创建和使用
            assert os.path.exists(temp_dir)
            assert len(os.listdir(temp_dir)) > 0

    def test_none_values(self):
        """测试 None 值的缓存处理"""
        @disk_cache()
        def return_none(arg=None):
            return arg

        assert return_none() is None
        assert return_none(None) is None
        assert return_none(42) == 42

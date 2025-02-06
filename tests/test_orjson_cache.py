import json
import time
import unittest
from datetime import datetime
from unittest.mock import Mock, patch
import functools

from loguru import logger
from ycache import orjson_lru_cache

logger.add('output/log/test_orjson_cache_{time}.log', retention=1)


class TestOrjsonLruCache(unittest.TestCase):
    def setUp(self):
        """每个测试用例前运行"""
        self.call_count = 0

    def test_basic_caching(self):
        """测试基本的缓存功能"""
        @orjson_lru_cache()
        def cached_func(x, y):
            self.call_count += 1
            return {"result": x + y}

        # 第一次调用
        result1 = cached_func(1, 2)
        self.assertEqual(result1, {"result": 3})
        self.assertEqual(self.call_count, 1)

        # 第二次调用应该命中缓存
        result2 = cached_func(1, 2)
        self.assertEqual(result2, {"result": 3})
        self.assertEqual(self.call_count, 1)  # 计数不应增加

        # 不同参数应该触发新的计算
        result3 = cached_func(2, 3)
        self.assertEqual(result3, {"result": 5})
        self.assertEqual(self.call_count, 2)

    def test_ttl_expiration(self):
        """测试缓存过期功能"""
        @orjson_lru_cache(ttl=1)  # 1秒后过期
        def cached_func():
            self.call_count += 1
            return {"timestamp": time.time()}

        # 第一次调用
        result1 = cached_func()
        self.assertEqual(self.call_count, 1)

        # 立即再次调用，应该使用缓存
        result2 = cached_func()
        self.assertEqual(result1, result2)
        self.assertEqual(self.call_count, 1)

        # 等待缓存过期
        time.sleep(1.1)
        result3 = cached_func()
        self.assertNotEqual(result1, result3)
        self.assertEqual(self.call_count, 2)

    def test_typed_cache(self):
        """测试类型敏感的缓存"""
        @orjson_lru_cache(typed=True)
        def cached_func(x):
            self.call_count += 1
            return {"value": x}

        # 整数参数
        result1 = cached_func(1)
        self.assertEqual(result1, {"value": 1})
        self.assertEqual(self.call_count, 1)

        # 浮点数参数（相同值但不同类型）
        result2 = cached_func(1.0)
        self.assertEqual(result2, {"value": 1.0})
        self.assertEqual(self.call_count, 2)

    def test_maxsize_limit(self):
        """测试缓存大小限制"""
        @orjson_lru_cache(maxsize=2)
        def cached_func(n):
            self.call_count += 1
            return {"n": n}

        # 填充缓存
        cached_func(1)
        cached_func(2)
        cached_func(3)  # 这应该导致最早的缓存被移除

        # 验证缓存行为
        cached_func(2)  # 应该命中缓存
        cached_func(3)  # 应该命中缓存
        cached_func(1)  # 应该重新计算（因为之前被移除）

        self.assertEqual(self.call_count, 4)  # 1,2,3 + 重新计算的 1

    def test_complex_objects(self):
        """测试复杂对象的序列化"""
        @orjson_lru_cache()
        def cached_func(data):
            self.call_count += 1
            return {
                "data": data,
                "timestamp": datetime.now().isoformat()
            }

        test_data = {
            "list": [1, 2, 3],
            "dict": {"a": 1, "b": 2},
            "nested": {"x": [{"y": 1}]}
        }

        # 测试复杂对象缓存
        result1 = cached_func(test_data)
        result2 = cached_func(test_data)

        self.assertEqual(result1, result2)
        self.assertEqual(self.call_count, 1)

    def test_error_handling(self):
        """测试错误处理"""
        @orjson_lru_cache()
        def failing_func(should_fail=False):
            self.call_count += 1
            if should_fail:
                raise ValueError("预期的错误")
            return {"status": "ok"}

        # 测试正常情况
        result = failing_func(False)
        self.assertEqual(result, {"status": "ok"})

        # 测试异常情况
        with self.assertRaises(ValueError):
            failing_func(True)

        # 验证异常后的行为
        result = failing_func(False)
        self.assertEqual(result, {"status": "ok"})
        self.assertEqual(self.call_count, 2)

    def test_cache_info(self):
        """测试缓存信息功能"""
        @orjson_lru_cache(maxsize=2)
        def cached_func(n):
            return {"n": n}

        # 执行一些缓存操作
        cached_func(1)
        cached_func(1)  # 命中
        cached_func(2)
        cached_func(3)  # 应该移除 1

        cache_info = cached_func.cache_info()
        self.assertIsInstance(cache_info, functools._CacheInfo)
        self.assertEqual(cache_info.maxsize, 2)
        self.assertGreaterEqual(cache_info.hits, 1)

    def test_cache_clear(self):
        """测试缓存清理功能"""
        @orjson_lru_cache()
        def cached_func(n):
            self.call_count += 1
            return {"n": n}

        # 填充缓存
        cached_func(1)
        cached_func(2)
        self.assertEqual(self.call_count, 2)

        # 清理缓存
        cached_func.cache_clear()

        # 验证缓存被清理
        cached_func(1)
        cached_func(2)
        self.assertEqual(self.call_count, 4)


if __name__ == '__main__':
    unittest.main()
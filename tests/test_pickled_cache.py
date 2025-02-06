import time
import pytest
from ycache.core import pickled_lru_cache, DEFAULT_CACHE_SIZE, CacheException

def test_basic_cache():
    """测试基本的缓存功能"""
    call_count = 0
    
    @pickled_lru_cache()
    def cached_func(x):
        nonlocal call_count
        call_count += 1
        return x * 2
    
    # 第一次调用，应该执行函数
    assert cached_func(2) == 4
    assert call_count == 1
    
    # 第二次调用，应该使用缓存
    assert cached_func(2) == 4
    assert call_count == 1
    
    # 不同参数，应该执行函数
    assert cached_func(3) == 6
    assert call_count == 2

def test_ttl_expiration():
    """测试缓存过期功能"""
    call_count = 0
    
    @pickled_lru_cache(ttl=1)  # 1秒后过期
    def cached_func(x):
        nonlocal call_count
        call_count += 1
        return x * 2
    
    # 第一次调用
    assert cached_func(2) == 4
    assert call_count == 1
    
    # 立即再次调用，应该使用缓存
    assert cached_func(2) == 4
    assert call_count == 1
    
    # 等待缓存过期
    time.sleep(1.1)
    
    # 过期后调用，应该重新执行
    assert cached_func(2) == 4
    assert call_count == 2

def test_maxsize_limit():
    """测试缓存大小限制"""
    call_count = 0
    
    @pickled_lru_cache(maxsize=2)
    def cached_func(x):
        nonlocal call_count
        call_count += 1
        return x * 2
    
    # 填充缓存
    cached_func(1)
    cached_func(2)
    assert call_count == 2
    
    # 超出缓存大小
    cached_func(3)
    # 再次调用最早的值，应该重新计算
    cached_func(1)
    assert call_count == 4

def test_typed_cache():
    """测试类型敏感的缓存"""
    call_count = 0
    
    @pickled_lru_cache(typed=True)
    def cached_func(x):
        nonlocal call_count
        call_count += 1
        return x * 2
    
    # 整数参数
    assert cached_func(2) == 4
    assert call_count == 1
    
    # 浮点数参数，虽然值相同但类型不同
    assert cached_func(2.0) == 4.0
    assert call_count == 2

def test_complex_objects():
    """测试复杂对象的缓存"""
    call_count = 0
    
    @pickled_lru_cache()
    def cached_func(obj):
        nonlocal call_count
        call_count += 1
        return len(obj)
    
    # 测试列表
    assert cached_func([1, 2, 3]) == 3
    assert call_count == 1
    assert cached_func([1, 2, 3]) == 3
    assert call_count == 1
    
    # 测试字典
    assert cached_func({"a": 1, "b": 2}) == 2
    assert call_count == 2
    assert cached_func({"a": 1, "b": 2}) == 2
    assert call_count == 2

def test_cache_info():
    """测试缓存信息统计"""
    @pickled_lru_cache()
    def cached_func(x):
        return x * 2
    
    # 初始状态
    info = cached_func.cache_info()
    assert info.hits == 0
    assert info.misses == 0
    assert info.maxsize == DEFAULT_CACHE_SIZE
    assert info.currsize == 0
    
    # 执行一些操作
    cached_func(1)  # miss
    cached_func(1)  # hit
    cached_func(2)  # miss
    
    # 检查统计信息
    info = cached_func.cache_info()
    assert info.hits == 1
    assert info.misses == 2
    assert info.maxsize == DEFAULT_CACHE_SIZE
    assert info.currsize == 2

def test_cache_clear():
    """测试缓存清理功能"""
    call_count = 0
    
    @pickled_lru_cache()
    def cached_func(x):
        nonlocal call_count
        call_count += 1
        return x * 2
    
    # 填充缓存
    cached_func(1)
    cached_func(2)
    assert call_count == 2
    
    # 清理缓存
    cached_func.cache_clear()
    
    # 重新调用，应该重新计算
    cached_func(1)
    cached_func(2)
    assert call_count == 4

def test_error_handling():
    """测试错误处理"""
    @pickled_lru_cache()
    def cached_func(x):
        if x < 0:
            raise ValueError("Negative value")
        return x * 2
    
    # 正常情况
    assert cached_func(2) == 4
    
    # 异常情况
    with pytest.raises(ValueError):
        cached_func(-1)
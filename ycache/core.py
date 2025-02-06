import hashlib
import pickle
import time
import orjson  # 新增
from functools import lru_cache, wraps
from typing import Any, Tuple, Dict, Optional
from dataclasses import dataclass
import inspect

from diskcache import Cache
from loguru import logger
import xxhash
from functools import partial

# 常量配置
DEFAULT_TTL = 10
DEFAULT_CACHE_SIZE = 128
DEFAULT_CACHE_DIR = '.temp'


@dataclass
class CacheConfig:
    """缓存配置类"""
    ttl: int = DEFAULT_TTL
    maxsize: Optional[int] = DEFAULT_CACHE_SIZE
    typed: bool = False
    cache_dir: str = DEFAULT_CACHE_DIR


class CacheResult:
    """缓存结果包装类"""
    __slots__ = ('value', 'death')

    def __init__(self, value: Any, death: float):
        self.value = value
        self.death = death

    def is_expired(self) -> bool:
        return self.death < time.monotonic()

# 添加签名缓存


@lru_cache(maxsize=128)
def get_func_signature(func):
    """缓存函数签名"""
    return inspect.signature(func)


# 优化日志记录，使用惰性求值
# 使用 partial 包装 logger 方法，避免每次调用时的字符串格式化开销
# 只有在实际需要记录日志时才会执行格式化操作
logger.debug = partial(logger.debug, lazy=True)
logger.error = partial(logger.error, lazy=True)


def normalize_args(func, args: tuple, kwargs: dict) -> Tuple[tuple, dict]:
    """优化的参数标准化"""
    try:
        # 性能优化：对于简单参数（无关键字参数且参数数量少），跳过标准化过程
        # 可以避免 signature 绑定和默认值填充的开销
        if not kwargs and len(args) <= 2 and all(isinstance(x, (str, int, float, bool)) for x in args):
            return args, kwargs
        
        sig = get_func_signature(func)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        return bound_args.args, bound_args.kwargs
    except (ValueError, TypeError) as e:
        logger.error(f"参数标准化失败: {str(e)}")
        raise


class CacheBase:
    """优化的缓存基类"""

    def __init__(self, config: CacheConfig):
        self.config = config
        self._pickle_protocol = pickle.HIGHEST_PROTOCOL
        # 性能优化：创建一个可重用的 xxhash 对象
        # 避免重复创建 hash 对象的开销，通过 reset 方法重用
        self._xxh64 = xxhash.xxh64()

    def _fast_hash(self, data: str) -> str:
        """使用 xxhash 优化的哈希函数
        xxhash 比 Python 内置的 hash 和 hashlib.md5 都要快
        且具有更好的哈希分布性
        """
        self._xxh64.reset()  # 重置哈希状态以重用对象
        self._xxh64.update(data.encode('utf-8'))
        return self._xxh64.hexdigest()

    def _serialize(self, data: Any) -> bytes:
        """优化的序列化"""
        try:
            # 对简单类型直接转换
            if isinstance(data, (str, int, float, bool)):
                return str(data).encode('utf-8')
            return pickle.dumps(data, self._pickle_protocol)
        except (pickle.PickleError, TypeError) as e:
            logger.error(f"序列化失败: {str(e)}")
            raise

    def _deserialize(self, data: bytes) -> Any:
        """优化的反序列化"""
        try:
            # 尝试简单类型转换
            try:
                return data.decode('utf-8')
            except (UnicodeDecodeError, AttributeError):
                return pickle.loads(data)
        except (pickle.PickleError, TypeError) as e:
            logger.error(f"反序列化失败: {str(e)}")
            raise

    def _fast_hash(self, data: str) -> str:
        """快速哈希函数"""
        if len(data) < 100:
            return str(hash(data))
        return hashlib.md5(data.encode('utf-8')).hexdigest()


class CacheException(Exception):
    """缓存相关异常的基类"""
    pass

class SerializationError(CacheException):
    """序列化错误"""
    pass

class CacheOperationError(CacheException):
    """缓存操作错误"""
    pass

class BaseLRUCache:
    """LRU缓存装饰器的基类"""
    # 性能优化：使用 __slots__ 限制实例属性
    # 可以显著减少内存使用，并略微提升属性访问速度
    __slots__ = ('config', '_cache_handler')

    def __init__(self, maxsize=DEFAULT_CACHE_SIZE, typed=False, ttl=DEFAULT_TTL):
        """初始化缓存配置
        
        Args:
            maxsize: 缓存最大条目数
            typed: 是否区分参数类型
            ttl: 缓存生存时间（秒）
        """
        self.config = CacheConfig(ttl=ttl, maxsize=maxsize, typed=typed)
        self._cache_handler = None

    def __call__(self, func):
        # 性能优化：当 maxsize=0 时直接返回原函数
        # 避免不必要的装饰器开销
        if self.config.maxsize == 0:
            return func

        self._cache_handler = self._get_cache_handler()
        
        @lru_cache(maxsize=self.config.maxsize, typed=self.config.typed)
        def cached_func_with_ttl(serialized_args, serialized_kwargs) -> CacheResult:
            try:
                args = self._cache_handler._deserialize(serialized_args)
                kwargs = self._cache_handler._deserialize(serialized_kwargs)
                value = func(*args, **kwargs)
                death = time.monotonic() + self.config.ttl
                return CacheResult(value=value, death=death)
            except (SerializationError, CacheOperationError) as e:
                logger.error(f"缓存操作失败: {str(e)}")
                raise
            except Exception:
                raise

        @wraps(func)
        def _wrapper(*args, **kwargs):
            try:
                norm_args, norm_kwargs = normalize_args(func, args, kwargs)
                serialized_args = self._cache_handler._serialize(norm_args)
                serialized_kwargs = self._cache_handler._serialize(norm_kwargs)
                
                result = cached_func_with_ttl(serialized_args, serialized_kwargs)
                
                if result.is_expired():
                    cache_info = cached_func_with_ttl.cache_info()
                    logger.debug("缓存过期: hits={}, misses={}, maxsize={}, currsize={}",
                        cache_info.hits,
                        cache_info.misses,
                        cache_info.maxsize,
                        cache_info.currsize
                    )
                    cached_func_with_ttl.cache_clear()
                    result.value = func(*args, **kwargs)
                    result.death = time.monotonic() + self.config.ttl
                
                return result.value
            except SerializationError as e:
                logger.error(f"序列化失败: {str(e)}")
                return func(*args, **kwargs)
            except Exception:
                raise

        _wrapper.cache_info = cached_func_with_ttl.cache_info
        _wrapper.cache_clear = cached_func_with_ttl.cache_clear
        return _wrapper

    def _get_cache_handler(self):
        """获取缓存处理器，子类必须实现"""
        raise NotImplementedError

class PickledLRUCache(BaseLRUCache):
    """Pickle序列化的LRU缓存"""
    def __init__(self, maxsize=DEFAULT_CACHE_SIZE, typed=False, ttl=DEFAULT_TTL):
        super().__init__(maxsize=maxsize, typed=typed, ttl=ttl)
        
    def _get_cache_handler(self):
        return CacheBase(self.config)

class JsonLRUCache(BaseLRUCache):
    """JSON序列化的LRU缓存"""
    def __init__(self, maxsize=DEFAULT_CACHE_SIZE, typed=False, ttl=DEFAULT_TTL):
        super().__init__(maxsize=maxsize, typed=typed, ttl=ttl)
        
    def _get_cache_handler(self):
        return JsonCacheBase(self.config)

# 更新装饰器函数为类装饰器
import warnings

def pickled_lru_cache(maxsize=DEFAULT_CACHE_SIZE, typed=False, ttl=DEFAULT_TTL):
    """Pickle序列化的LRU缓存装饰器
    
    .. deprecated:: 1.0.0
        由于性能和安全性考虑，建议使用 :func:`orjson_lru_cache` 替代。
        `orjson_lru_cache` 提供更好的性能和更安全的序列化机制。
        
    Args:
        maxsize (int, optional): LRU 缓存的最大条目数。默认为 128。
        typed (bool, optional): 是否区分参数类型。默认为 False。
        ttl (int, optional): 缓存生存时间（秒）。默认为 10秒。
    """
    warnings.warn(
        "pickled_lru_cache 将在未来版本中废弃，建议使用 orjson_lru_cache 替代，"
        "它提供更好的性能和更安全的序列化机制。",
        DeprecationWarning,
        stacklevel=2
    )
    return PickledLRUCache(maxsize=maxsize, typed=typed, ttl=ttl)

def orjson_lru_cache(maxsize=DEFAULT_CACHE_SIZE, typed=False, ttl=DEFAULT_TTL):
    """JSON序列化的LRU缓存装饰器"""
    return JsonLRUCache(maxsize=maxsize, typed=typed, ttl=ttl)


def disk_cache(cache_dir=DEFAULT_CACHE_DIR, ttl=60*60*24):
    """优化的磁盘缓存装饰器"""
    config = CacheConfig(ttl=ttl, cache_dir=cache_dir)
    
    def _decorator(func):
        # 性能优化：使用线程本地存储
        # 避免多线程访问时的锁竞争
        # 每个线程维护自己的 Cache 实例
        from threading import local
        thread_local = local()
        cache_handler = CacheBase(config)
        
        def get_cache():
            # 延迟初始化：仅在首次访问时创建 Cache 实例
            if not hasattr(thread_local, 'cache'):
                thread_local.cache = Cache(config.cache_dir)
            return thread_local.cache

        def make_key(namespace: str, args: tuple, kwargs: dict) -> str:
            """优化的键生成"""
            try:
                norm_args, norm_kwargs = normalize_args(func, args, kwargs)
                key_data = f"{namespace}-{str(norm_args)}-{str(norm_kwargs)}"
                return cache_handler._fast_hash(key_data)
            except Exception as e:
                logger.error(f"键生成失败: {str(e)}")
                raise

        @wraps(func)
        def _wrapper(*args, **kwargs):
            try:
                key = make_key(func.__name__, args, kwargs)
                cache = get_cache()
                cached_result = cache.get(key)
                if cached_result is None:
                    result = func(*args, **kwargs)
                    cache.set(key, result, expire=config.ttl)
                    return result
                return cached_result
            except Exception as e:
                logger.error(f"磁盘缓存操作失败: {str(e)}")
                return func(*args, **kwargs)

        return _wrapper
    return _decorator


class JsonCacheBase(CacheBase):
    """JSON 缓存基类"""

    def _serialize(self, data: Any) -> bytes:
        """使用 orjson 进行序列化"""
        try:
            return orjson.dumps(
                data,
                option=orjson.OPT_SERIALIZE_NUMPY |
                orjson.OPT_SERIALIZE_DATACLASS |
                orjson.OPT_PASSTHROUGH_DATETIME
            )
        except TypeError as e:
            logger.error(f"JSON序列化失败: {str(e)}")
            raise

    def _deserialize(self, data: bytes) -> Any:
        """使用 orjson 进行反序列化"""
        try:
            return orjson.loads(data)
        except TypeError as e:
            logger.error(f"JSON反序列化失败: {str(e)}")
            raise


def orjson_lru_cache(maxsize=DEFAULT_CACHE_SIZE, typed=False, ttl=DEFAULT_TTL):
    """基于 orjson 的 LRU 缓存装饰器
    
    这个装饰器使用 orjson 进行序列化，相比 pickle 具有更好的性能。
    注意：仅支持可 JSON 序列化的数据类型。
    
    Args:
        maxsize (int, optional): LRU 缓存的最大条目数。默认为 128。
        typed (bool, optional): 是否区分参数类型。默认为 False。
        ttl (int, optional): 缓存生存时间（秒）。默认为 10秒。
    """
    config = CacheConfig(ttl=ttl, maxsize=maxsize, typed=typed)

    def _decorator(func):
        cache_handler = JsonCacheBase(config)

        @lru_cache(maxsize=config.maxsize, typed=config.typed)
        def cached_func_with_ttl(serialized_args, serialized_kwargs) -> CacheResult:
            args = cache_handler._deserialize(serialized_args)
            kwargs = cache_handler._deserialize(serialized_kwargs)

            try:
                value = func(*args, **kwargs)
                death = time.monotonic() + config.ttl
                return CacheResult(value=value, death=death)
            except Exception:
                # 移除这里的日志，让异常正常传播
                raise

        @wraps(func)
        def _wrapper(*args, **kwargs):
            try:
                norm_args, norm_kwargs = normalize_args(func, args, kwargs)
                serialized_args = cache_handler._serialize(norm_args)
                serialized_kwargs = cache_handler._serialize(norm_kwargs)

                result = cached_func_with_ttl(serialized_args, serialized_kwargs)

                if result.is_expired():
                    cache_info = cached_func_with_ttl.cache_info()
                    logger.debug("缓存过期: hits={}, misses={}, maxsize={}, currsize={}",
                        cache_info.hits,
                        cache_info.misses,
                        cache_info.maxsize,
                        cache_info.currsize
                    )
                    cached_func_with_ttl.cache_clear()
                    result.value = func(*args, **kwargs)
                    result.death = time.monotonic() + config.ttl

                return result.value
            except (pickle.PickleError, TypeError) as e:
                # 只有序列化相关的错误才需要降级
                logger.error(f"缓存操作失败: {str(e)}")
                return func(*args, **kwargs)
            except Exception:
                # 其他异常正常传播
                raise

        _wrapper.cache_info = cached_func_with_ttl.cache_info
        _wrapper.cache_clear = cached_func_with_ttl.cache_clear
        return _wrapper

    return _decorator
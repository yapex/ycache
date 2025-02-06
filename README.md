# YCache

YCache 是一个高性能的 Python 缓存工具库，提供了内存缓存和磁盘缓存的实现，支持 TTL（生存时间）和 LRU（最近最少使用）淘汰策略。

## 特性

- 🚀 高性能：使用 xxhash 进行快速哈希计算
- 💾 多种存储：支持内存缓存和磁盘缓存
- 🔄 序列化选项：支持 pickle 和 orjson 序列化
- ⏱️ TTL 支持：可设置缓存项的过期时间
- 🎯 类型感知：支持参数类型敏感的缓存
- 🧵 线程安全：磁盘缓存支持多线程访问

## 安装
```bash
pip install ycache
```
## 快速开始
### 内存缓存

```python
from ycache import orjson_lru_cache

@orjson_lru_cache(maxsize=128, ttl=60)
def expensive_operation(x: int) -> int:
    # 一些耗时的操作
    return x * 2

result = expensive_operation(42)  # 执行函数
result = expensive_operation(42)  # 使用缓存
```
### 磁盘缓存
```python
from ycache import disk_cache

@disk_cache(cache_dir='.cache', ttl=3600)
def load_data(filename: str) -> dict:
    # 一些耗时的文件操作
    return {'data': 'content'}

data = load_data('example.txt')
```
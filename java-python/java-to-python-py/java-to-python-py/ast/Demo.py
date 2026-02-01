# full_syntax_demo.py

"""模块文档字符串示例"""

# —— 导入 —— #
import os
import sys
from collections import defaultdict, namedtuple
from typing import (
    Any, Union, Optional, List, Dict, Tuple, Callable,
    TypeVar, Generic, Protocol
)
from dataclasses import dataclass, field
from functools import lru_cache, wraps
from contextlib import contextmanager, suppress
import asyncio

# —— 常量、类型变量 —— #
PI: float = 3.14159
EULER = 2.71828
T = TypeVar('T')
U = TypeVar('U', bound=int)

# —— 全局变量 与 简单表达式 —— #
counter = 0
square = lambda x: x * x

# —— 装饰器 示例 —— #
def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args, **kwargs):
        print(f"Calling {func.__name__}")
        return func(*args, **kwargs)
    return wrapper

# —— 上下文管理器 示例 —— #
@contextmanager
def managed_resource(name: str):
    print(f"Acquire {name}")
    try:
        yield {"resource": name}
    finally:
        print(f"Release {name}")

# —— 数据类 示例 —— #
@dataclass
class Point:
    x: float
    y: float = 0.0
    tags: List[str] = field(default_factory=list)

    def move(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    @property
    def coords(self) -> Tuple[float, float]:
        return (self.x, self.y)

# —— 元类 示例 —— #
class Meta(type):
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        cls.created = True
        return cls

class Example(metaclass=Meta):
    pass

# —— 协议（Protocol）示例 —— #
class Serializer(Protocol):
    def serialize(self) -> str:
        ...

@dataclass
class DataSerializer:
    data: Any
    def serialize(self) -> str:
        return str(self.data)

# —— 泛型 类 示例 —— #
class Box(Generic[T]):
    def __init__(self, content: T):
        self.content = content

# —— 生成器 与 迭代器 示例 —— #
def countdown(n: int) -> Any:
    while n > 0:
        yield n
        n -= 1

# —— 异步 示例 —— #
async def async_double(x: int) -> int:
    await asyncio.sleep(0)
    return x * 2

async def async_main():
    results = [await async_double(i) for i in range(5)]
    return results

# —— 复合 控制流 与 异常处理 —— #
def complex_logic(data: Dict[str, Any]) -> None:
    try:
        value = data.get("key") or 0
        match value:
            case 0:
                print("Zero")
            case [] | {}:
                print("Empty")
            case int(i) if i > 0:
                print(f"Positive {i}")
            case [first, *rest]:
                print(f"List head {first}, tail {rest}")
            case {"x": x, "y": y}:
                print(f"Point {x},{y}")
            case _:
                raise ValueError("Unsupported pattern")
    except ValueError as e:
        print("Error:", e)
    finally:
        print("Finished")

# —— 推导式 与 赋值表达式 —— #
squares = [i * i for i in range(10)]
evens = {i for i in range(10) if i % 2 == 0}
mapping = {str(i): i for i in range(5)}

if (n := len(squares)) > 5:
    print("Long list")

# —— 私有与魔术方法 示例 —— #
class Fancy:
    def __init__(self, name: str):
        self._name = name

    def __repr__(self):
        return f"Fancy({self._name!r})"

# —— 主入口 —— #
if __name__ == "__main__":
    print(__doc__)
    p = Point(1, 2, ["start"])
    p.move(3, 4)
    print("Point coords:", p.coords)

    with managed_resource("res1") as r:
        print("Using", r)

    box = Box
    print("Box content:", box.content)

    for num in countdown(3):
        print("Countdown:", num)

    # 运行异步
    results = asyncio.run(async_main())
    print("Async results:", results)

    complex_logic({"key": [1, 2, 3]})
    print("Squares:", squares)
    print("Evens:", evens)
    print("Mapping:", mapping)

    fancy = Fancy("test")
    print(f"Fancy repr: {fancy}")

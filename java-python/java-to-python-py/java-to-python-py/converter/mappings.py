from typing import Dict, Optional, Tuple, Any

API_MAP: Dict[str, Dict[str, Any]] = {
    # ---------- Collections & Lists ----------
    "List": {
        "fqn": "java.util.List",
        "type": "list",
        "methods": {
            "add": "append",
            "addAll": "extend",
            "remove": "remove",       # value
            "get": "__getitem__",
            "set": "__setitem__",
            "size": "len",
            "isEmpty": "not",
            "contains": "__contains__",
            "containsAll": "contains_all",
            "indexOf": "index",
            "clear": "clear",
            "toArray": "list",
            "subList": "slice",
            "iterator": "iter",
            "sort": "sort",
            "forEach": "for_each",
            "replaceAll": "map_inplace",
            "removeIf": "filter_inplace",
        },
    },
    "ArrayList": {
        "fqn": "java.util.ArrayList",
        "type": "list",
        "methods": {
            "add": "append", "addAll": "extend", "get": "__getitem__", "set": "__setitem__",
            "remove": "remove", "size": "len", "clear": "clear", "toArray": "list"
        },
    },
    "LinkedList": {
        "fqn": "java.util.LinkedList",
        "type": "list",
        "methods": {
            "add": "append",
            "addFirst": "insert(0, ...)",
            "addLast": "append",
            "removeFirst": "pop(0)",
            "removeLast": "pop",
            "getFirst": "[0]",
            "getLast": "[-1]",
            "size": "len",
            "iterator": "iter",
            "offer": "append",
            "poll": "popleft"
        },
        "notes": "可映射到 list 或 collections.deque"
    },
    "Vector": {
        "fqn": "java.util.Vector",
        "type": "list",
        "methods": {"add": "append", "remove": "remove", "get": "__getitem__", "size": "len"},
    },

    # ---------- Set ----------
    "Set": {
        "fqn": "java.util.Set",
        "type": "set",
        "methods": {
            "add": "add",
            "remove": "remove",
            "contains": "__contains__",
            "containsAll": "contains_all",
            "size": "len",
            "isEmpty": "not",
            "iterator": "iter",
            "clear": "clear",
            "addAll": "update",
            "retainAll": "intersection_update",
            "forEach": "for_each",
        },
    },
    "HashSet": {"fqn": "java.util.HashSet", "type": "set", "methods": {"add": "add", "remove": "remove", "contains": "__contains__"}},
    "TreeSet": {"fqn": "java.util.TreeSet", "type": "set", "methods": {"add": "add", "first": "min", "last": "max"}},

    # ---------- Map ----------
    "Map": {
        "fqn": "java.util.Map",
        "type": "dict",
        "methods": {
            "put": "update_put",
            "putIfAbsent": "setdefault",
            "get": "get",
            "getOrDefault": "get",
            "remove": "pop",
            "containsKey": "__contains__",
            "containsValue": "contains_value",
            "containsAll": "contains_all",
            "size": "len",
            "isEmpty": "not",
            "keySet": "keys",
            "values": "values",
            "entrySet": "items",
            "putAll": "update",
            "clear": "clear",
            "forEach": "for_each",
        },
    },
    "HashMap": {"fqn": "java.util.HashMap", "type": "dict", "methods": {"put": "update_put", "get": "get", "remove": "pop"}},
    "LinkedHashMap": {"fqn": "java.util.LinkedHashMap", "type": "dict", "methods": {"put": "update_put"}},
    "TreeMap": {"fqn": "java.util.TreeMap", "type": "dict", "methods": {"put": "update_put"}},

    # ---------- Queue / Deque ----------
    "Queue": {"fqn": "java.util.Queue", "type": "collections.deque", "methods": {"offer": "append", "poll": "popleft", "peek": "peek"}},
    "Deque": {"fqn": "java.util.Deque", "type": "collections.deque", "methods": {"addFirst": "appendleft", "addLast": "append", "pollFirst": "popleft", "pollLast": "pop"}},
    "ArrayDeque": {"fqn": "java.util.ArrayDeque", "type": "collections.deque", "methods": {"add": "append", "offer": "append", "poll": "popleft"}},
    "PriorityQueue": {
        "fqn": "java.util.PriorityQueue",
        "type": "list",
        "methods": {
            "add": "append",
            "offer": "append",
            "poll": "pop0",
            "peek": "peek",
            "isEmpty": "not",
            "size": "len",
        },
    },

    # ---------- Arrays & Collections ----------
    "Arrays": {
        "fqn": "java.util.Arrays",
        "type": None,
        "static": {
            "asList": "list({args})",
            "copyOf": "list({args})",
            "sort": "sorted({args})",
            "toString": "str({args})"
        },
    },
    "Collections": {
        "fqn": "java.util.Collections",
        "type": None,
        "static": {
            "sort": "list.sort()",
            "reverse": "list.reverse()",
            "shuffle": "random.shuffle(list)",
            "emptyList": "[]",
            "singletonList": "[{args}]",
            "unmodifiableList": "tuple({args})",
            "max": "max({args})",
            "min": "min({args})"
        },
    },

    # ---------- Optional ----------
    "Optional": {
        "fqn": "java.util.Optional",
        "type": "Optional",
        "methods": {
            "isPresent": "is_not_none",
            "ifPresent": "if value is not None: ...",
            "orElse": "or_else",
            "orElseGet": "or_else_get",
            "ofNullable": "maybe"
        }
    },

    # ---------- Others ----------
    "Objects": {
        "fqn": "java.util.Objects",
        "static": {
            "requireNonNull": "assert {args} is not None",
            "equals": "{a} == {b}",
            "hash": "hash({args})"
        }
    },
    "Math": {
        "fqn": "java.lang.Math",
        "static": {
            "max": "max({args})",
            "min": "min({args})",
            "abs": "abs({args})",
            "pow": "pow({args})",
            "sqrt": "math.sqrt({args})",
            "ceil": "math.ceil({args})",
            "floor": "math.floor({args})",
            "random": "random.random()",
        },
    },
    "StringJoiner": {"fqn": "java.util.StringJoiner", "type": "str", "methods": {"add": "append", "toString": "str"}},
    "StringTokenizer": {"fqn": "java.util.StringTokenizer", "type": "iter(str.split)", "methods": {"nextToken": "next", "hasMoreTokens": "has_next"}},
    "Scanner": {"fqn": "java.util.Scanner", "type": "iter", "methods": {"nextLine": "input()", "nextInt": "int(input())", "hasNext": "has_next"}},

    "Date": {"fqn": "java.util.Date", "type": "datetime.datetime", "methods": {"getTime": "timestamp"}},
    "Calendar": {"fqn": "java.util.Calendar", "type": "datetime.datetime"},
    "Random": {"fqn": "java.util.Random", "type": "random.Random", "methods": {"nextInt": "randint", "nextDouble": "random()"}},
    "UUID": {"fqn": "java.util.UUID", "type": "uuid.UUID", "static": {"randomUUID": "uuid.uuid4()"}},
    "Formatter": {"fqn": "java.util.Formatter", "type": "str.format"},
    "Properties": {"fqn": "java.util.Properties", "type": "dict", "methods": {"getProperty": "get", "setProperty": "setdefault"}},
    "Timer": {"fqn": "java.util.Timer", "type": "threading.Timer"},
    "TimerTask": {"fqn": "java.util.TimerTask", "type": "callable"},
    "Stack": {"fqn": "java.util.Stack", "type": "list", "methods": {"push": "append", "pop": "pop", "peek": "[-1]"}},
    "Dictionary": {"fqn": "java.util.Dictionary", "type": "dict"},
    "BitSet": {"fqn": "java.util.BitSet", "type": "set", "methods": {"set": "add", "get": "in"}},

    "OptionalInt": {"fqn": "java.util.OptionalInt", "type": "Optional[int]"},
    "OptionalLong": {"fqn": "java.util.OptionalLong", "type": "Optional[int]"},
    "OptionalDouble": {"fqn": "java.util.OptionalDouble", "type": "Optional[float]"},
    "Spliterator": {"fqn": "java.util.Spliterator", "type": "iterator"},
    "Comparator": {"fqn": "java.util.Comparator", "type": "callable", "methods": {"reversed": "reversed comparator"}},
    "Observer": {"fqn": "java.util.Observer", "type": "callable"},
    "Observable": {"fqn": "java.util.Observable", "type": "pubsub"},
}

TYPE_ALIASES: Dict[str, str] = {
    "List": "List",
    "ArrayList": "ArrayList",
    "LinkedList": "LinkedList",
    "Set": "Set",
    "HashSet": "HashSet",
    "Map": "Map",
    "HashMap": "HashMap",
    "TreeMap": "TreeMap",
    "Queue": "Queue",
    "Deque": "Deque",
    "ArrayDeque": "ArrayDeque",
    "PriorityQueue": "PriorityQueue",
    "Iterator": "Iterator",
    "Optional": "Optional",
    "Properties": "Properties",
    "Date": "Date",
    "UUID": "UUID",
    "String": "str",
    "Integer": "int",
    "int": "int",
    "long": "int",
    "double": "float",
    "float": "float",
    "boolean": "bool",
    "Boolean": "bool",
    "Object": "Any",
    "void": "None",
}

def map_type(java_type: Optional[str]) -> Optional[str]:
    if java_type is None:
        return None
    jt = str(java_type).strip()
    if jt.endswith("[]"):
        base = jt[:-2]
        return f"list[{map_type(base) or 'Any'}]"
    if "<" in jt and ">" in jt:
        base = jt.split("<", 1)[0].strip()
        inner = jt[jt.find("<")+1:jt.rfind(">")]
        inner_mapped = map_type(inner.split(",")[0].strip()) or "Any"
        base_key = TYPE_ALIASES.get(base, base)
        mapped = API_MAP.get(base_key, {}).get("type") or TYPE_ALIASES.get(base_key)
        if mapped:
            return f"{mapped}[{inner_mapped}]" if "[" not in mapped else f"{mapped}"
        if base.lower().endswith("list"):
            return f"list[{inner_mapped}]"
        if base.lower().endswith("set"):
            return f"set[{inner_mapped}]"
        if base.lower().endswith("map"):
            return f"dict[{inner_mapped}, Any]"
        return f"{base}[{inner_mapped}]"
    if "." in jt:
        short = jt.split(".")[-1]
        if short in API_MAP:
            typ = API_MAP[short].get("type")
            return typ
        return TYPE_ALIASES.get(short, short)
    if jt in TYPE_ALIASES:
        return TYPE_ALIASES[jt]
    if jt in API_MAP:
        return API_MAP[jt].get("type")
    basic = {
        "int": "int", "Integer": "int", "long": "int",
        "double": "float", "float": "float",
        "boolean": "bool", "Boolean": "bool",
        "char": "str", "String": "str", "Object": "Any"
    }
    if jt in basic:
        return basic[jt]
    return jt

def map_fqn(shortname: str) -> Optional[str]:
    entry = API_MAP.get(shortname)
    if entry:
        return entry.get("fqn")
    return None

def map_method(owner: Optional[str], method: str):
    m = method or ""
    if owner:
        own = owner.split(".")[-1] if "." in owner else owner
        if own in API_MAP:
            methods = API_MAP[own].get("methods", {})
            if m in methods:
                return methods[m], f"mapped {own}.{m}"
            static = API_MAP[own].get("static", {})
            if m in static:
                return static[m], f"mapped static {own}.{m}"
    common_map = {
        "add": "append",
        "addAll": "extend",
        "remove": "remove",
        "get": "__getitem__",
        "put": "update_put",
        "containsAll": "contains_all",
        "size": "len",
        "isEmpty": "not",
        "contains": "__contains__",
        "iterator": "iter",
        "forEach": "for_each",
        "println": "print",
        "toString": "str",
        "equals": "==",
        "hashCode": "hash",
        "length": "len"
    }
    if m in common_map:
        return common_map[m], "fallback"
    return None, None

def map_static(fqcn: str, method: str):
    if not fqcn:
        return None, None
    short = fqcn.split(".")[-1]
    entry = API_MAP.get(short)
    if entry:
        static = entry.get("static", {})
        if method in static:
            return static[method], f"static {short}.{method}"
    for key, val in API_MAP.items():
        if val.get("fqn") == fqcn and "static" in val:
            if method in val["static"]:
                return val["static"][method], f"static {fqcn}.{method}"
    fallback = {
        ("Collections", "sort"): "sorted({args})",
        ("Collections", "reverse"): "list(reversed({args}))",
        ("Arrays", "asList"): "list({args})",
    }
    if (short, method) in fallback:
        return fallback[(short, method)], "fallback"
    return None, None

def find_methods_by_name(method_name: str) -> Dict[str, str]:
    results = {}
    for cls, info in API_MAP.items():
        methods = info.get("methods", {})
        if method_name in methods:
            results[cls] = methods[method_name]
    return results

def summarize_api_map() -> str:
    class_count = len(API_MAP)
    method_count = sum(len(v.get("methods", {})) + len(v.get("static", {})) for v in API_MAP.values())
    return f"API_MAP classes: {class_count}, total method/static mappings: {method_count}"

__all__ = [
    "API_MAP", "TYPE_ALIASES", "map_type", "map_method", "map_static",
    "map_fqn", "find_methods_by_name", "summarize_api_map"
]

from typing import List

class LiteralConverter:
    """Convert literal-like nodes to python literal strings."""
    def convert(self, node) -> List[str]:
        val = node.get("name")
        if val is None:
            return ["None"]
        if isinstance(val, str) and val.startswith("\"") and val.endswith("\""):
            return [val]
        return [repr(val)]

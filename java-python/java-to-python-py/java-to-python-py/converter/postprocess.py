import re
from typing import List

def _remove_adjacent_duplicate_lines(lines: List[str]) -> List[str]:
    out, prev = [], None
    for ln in lines:
        s = ln.rstrip("\n")
        if prev is not None and s == prev:
            continue
        out.append(ln); prev = s
    return out

def _extract_method_block(lines: List[str], start_idx: int):
    def is_deco(i): return i >= 0 and re.match(r"^\s{4}@", lines[i]) is not None
    deco_start = start_idx
    while is_deco(deco_start - 1):
        deco_start -= 1

    def_line = lines[start_idx]
    m = re.match(r"^(\s*)def\s+\w+\s*\(.*\)\s*:", def_line)
    if not m:
        return start_idx, [], start_idx
    base_indent = len(m.group(1))
    block = lines[deco_start:start_idx+1]
    i = start_idx + 1
    while i < len(lines):
        ln = lines[i]
        if ln.strip() == "":
            block.append(ln); i += 1; continue
        indent = len(ln) - len(ln.lstrip(' '))
        if indent <= base_indent - 1:
            break
        block.append(ln); i += 1
    return i - 1, block, deco_start

def _unindent_block(block: List[str], remove_spaces: int) -> List[str]:
    out = []
    for ln in block:
        if ln.strip() == "":
            out.append("\n"); continue
        cur_lead = len(ln) - len(ln.lstrip(' '))
        cut = min(cur_lead, remove_spaces)
        out.append(ln[cut:])
    return out

def model_patch_code(code: str) -> str:
    lines = code.splitlines(keepends=True)
    i = 0
    new_lines = []
    extracted_main = None

    while i < len(lines):
        ln = lines[i]
        if re.match(r"^\s{4}def\s+main\s*\(", ln) or (
            re.match(r"^\s{4}@", ln) and i+1 < len(lines) and re.match(r"^\s{4}def\s+main\s*\(", lines[i+1])
        ):
            def_idx = i if re.match(r"^\s{4}def\s+main", ln) else i+1
            end_idx, block, block_start = _extract_method_block(lines, def_idx)
            block = _remove_adjacent_duplicate_lines(block)
            unindented = _unindent_block(block, 4)

            # 去掉装饰器（如 @staticmethod）
            unindented = [l for l in unindented if not l.lstrip().startswith("@")]

            # 签名改造
            sig = unindented[0]
            sig_new = re.sub(r"def\s+main\s*\(\s*self\s*,?", "def main(", sig)
            sig_new = re.sub(r"def\s+main\s*\(\s*\)", "def main(args=None)", sig_new)
            unindented[0] = sig_new

            body = "".join(unindented).replace("self.", "instance.")
            extracted_main = body
            i = end_idx + 1
            continue
        else:
            new_lines.append(ln); i += 1

    out = "".join(new_lines)
    out_lines = _remove_adjacent_duplicate_lines(out.splitlines(keepends=True))
    out = "".join(out_lines)

    if extracted_main:
        out = out.rstrip() + "\n\n" + extracted_main.rstrip() + "\n\nif __name__ == \"__main__\":\n    main()\n"
    else:
        if "if __name__ == \"__main__\"" not in out:
            out = out.rstrip() + "\n\nif __name__ == \"__main__\":\n    pass\n"
    return out

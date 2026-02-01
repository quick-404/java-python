import argparse
import json
import re
from pathlib import Path

from converter.converter import Converter

def main():
    parser = argparse.ArgumentParser(description="Convert Java AST JSON to Python.")
    parser.add_argument("in_ast", help="Path to the Java AST JSON file.")
    parser.add_argument("out_py", nargs="?", default="converted.py", help="Output Python file path.")
    parser.add_argument(
        "--split-blocks",
        action="store_true",
        help="Split converted top-level blocks (class/def/main-guard) into separate files.",
    )
    parser.add_argument(
        "--split-dir",
        default=None,
        help="Output directory for split blocks (defaults to <out_py stem>_blocks).",
    )
    args = parser.parse_args()

    in_json = args.in_ast
    out_py = args.out_py

    with open(in_json, encoding="utf-8") as f:
        ast = json.load(f)
    conv = Converter(ast)
    result = conv.run(in_json, out_py)

    if args.split_blocks:
        blocks = (result.get("syntax") or {}).get("blocks", [])
        if not blocks:
            print("⚠️ 未发现可拆分的顶层块。")
            return
        out_path = Path(out_py)
        split_dir = Path(args.split_dir) if args.split_dir else out_path.with_suffix("").with_name(
            f"{out_path.stem}_blocks"
        )
        split_dir.mkdir(parents=True, exist_ok=True)
        for idx, blk in enumerate(blocks, start=1):
            name = blk.get("name", f"block_{idx}")
            safe = re.sub(r"[^0-9A-Za-z_]+", "_", name).strip("_") or f"block_{idx}"
            out_file = split_dir / f"{idx:02d}_{safe}.py"
            out_file.write_text(blk.get("code", "").rstrip() + "\n", encoding="utf-8")
        print(f"✅ 已拆分输出到: {split_dir}")

if __name__ == "__main__":
    main()

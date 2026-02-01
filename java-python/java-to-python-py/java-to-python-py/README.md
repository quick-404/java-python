# Java AST to Python Converter

This repository contains a converter that takes a Java abstract syntax tree (AST) in JSON form and generates runnable Python code.

## Prerequisites
- Python 3.10+ (standard library only; no extra dependencies).

## Converting a Java AST
1. Prepare a Java AST JSON file. The repository includes `ast_Demo.json` as an example input.
2. Run the converter:
   ```bash
   python run_converter.py <in_ast.json> [out_py]
   ```
   - `<in_ast.json>`: path to the Java AST JSON file.
   - `[out_py]`: optional output path for the generated Python file (defaults to `converted.py`).

Example using the bundled sample:
```bash
python run_converter.py ast_Demo.json
```
This command writes the translated Python code to `converted.py`.
The converter also appends a comment block to the end of the output file with the latest conversion report.

### Splitting converted blocks
If you want to split the converted output into top-level blocks (classes/functions/main guard), add:
```bash
python run_converter.py ast_Demo.json converted.py --split-blocks
```
By default the blocks are written to `<out_py stem>_blocks/`. You can override the directory:
```bash
python run_converter.py ast_Demo.json converted.py --split-blocks --split-dir out_blocks
```

## Running the Generated Code
After conversion, execute the generated Python file directly:
```bash
python converted.py
```
If the Java source contained a static `main` method, the translated `main` accepts optional arguments and will run even when no command-line parameters are provided.

## Regenerating After Changes
If you edit converter logic or the input AST, rerun the converter to refresh the output file before executing it.

## Understanding the conversion report
Each run prints a short report to help you gauge translation quality:

- **Efficiency**: ratio of actionable Java nodes that produced meaningful Python code (target ≥ 0.8).
- **Parsability**: share of top-level classes/functions/guards that pass Python syntax checks via `ast.parse`.
- **Lines**: number of translated lines emitted before post-processing.
- **Time**: wall-clock time to parse the JSON AST and generate the Python code.

Use these numbers to spot regressions when you tweak mappings or add new Java constructs to the converter.

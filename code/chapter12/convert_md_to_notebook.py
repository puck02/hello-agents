#!/usr/bin/env python3
"""
Convert chapter12 markdown to Jupyter notebook format.
"""
import json
import re
import sys
import uuid

def make_cell_id():
    return uuid.uuid4().hex[:12]

def convert_md_to_notebook(md_path, nb_path):
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    cells = []
    current_md_lines = []
    current_code_lines = []
    in_code_block = False
    code_lang = ''
    fence_pattern = None  # The opening fence string (e.g., '```' or '````')

    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]

        if not in_code_block:
            # Detect the start of a code fence (3 or 4 backticks)
            m = re.match(r'^(`{3,4})([\w\-]*)\s*$', line)
            if m:
                fence = m.group(1)   # ``` or ````
                lang = m.group(2)
                # Start a code block: flush current markdown first
                if current_md_lines:
                    md_source = '\n'.join(current_md_lines)
                    # Strip trailing blank lines
                    md_source = md_source.rstrip('\n')
                    if md_source.strip():
                        cells.append({
                            "cell_type": "markdown",
                            "id": make_cell_id(),
                            "metadata": {},
                            "source": md_source
                        })
                    current_md_lines = []
                in_code_block = True
                fence_pattern = fence
                code_lang = lang
                i += 1
                continue
            else:
                current_md_lines.append(line)
        else:
            # Inside a code block, look for matching closing fence
            # A closing fence must be EXACTLY the same fence string (or longer)
            stripped = line.rstrip()
            if stripped == fence_pattern or (len(stripped) >= len(fence_pattern) and
                    all(c == '`' for c in stripped) and len(stripped) >= len(fence_pattern) and
                    stripped == fence_pattern):
                # End of code block
                code_source = '\n'.join(current_code_lines)
                if code_source.strip():
                    cells.append({
                        "cell_type": "code",
                        "id": make_cell_id(),
                        "metadata": {},
                        "execution_count": None,
                        "outputs": [],
                        "source": code_source,
                        "lang": code_lang
                    })
                current_code_lines = []
                in_code_block = False
                code_lang = ''
                fence_pattern = None
            else:
                current_code_lines.append(line)
        i += 1

    # Flush remaining markdown
    if current_md_lines:
        md_source = '\n'.join(current_md_lines).rstrip('\n')
        if md_source.strip():
            cells.append({
                "cell_type": "markdown",
                "id": make_cell_id(),
                "metadata": {},
                "source": md_source
            })

    # Post-process cells: for bash code, add a comment header; also convert source to list
    final_cells = []
    for cell in cells:
        if cell['cell_type'] == 'code':
            lang = cell.pop('lang', '')
            source = cell['source']
            # For shell/bash code, add a comment to indicate it's a bash command
            if lang in ('bash', 'sh', 'shell'):
                lines_of_code = source.split('\n')
                # Add shebang-like comment only if not already present
                if lines_of_code and not lines_of_code[0].startswith('#'):
                    source = '# 以下为终端命令（Terminal Commands）\n' + source
            # Convert source to list format (each line as separate string)
            source_lines = source.split('\n')
            cell['source'] = [l + '\n' if idx < len(source_lines)-1 else l
                              for idx, l in enumerate(source_lines)]
            final_cells.append(cell)
        else:
            # Markdown cell: convert source to list format
            source = cell['source']
            source_lines = source.split('\n')
            cell['source'] = [l + '\n' if idx < len(source_lines)-1 else l
                              for idx, l in enumerate(source_lines)]
            final_cells.append(cell)

    # Build notebook structure
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "name": "python",
                "version": "3.10.0"
            }
        },
        "cells": final_cells
    }

    with open(nb_path, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, ensure_ascii=False, indent=1)

    print(f"✅ 转换完成！共生成 {len(final_cells)} 个单元格")
    code_cells = sum(1 for c in final_cells if c['cell_type'] == 'code')
    md_cells = sum(1 for c in final_cells if c['cell_type'] == 'markdown')
    print(f"   - Markdown 单元格: {md_cells}")
    print(f"   - 代码单元格: {code_cells}")
    print(f"   输出文件: {nb_path}")


if __name__ == '__main__':
    md_path = '/root/workspace/hello-agents/docs/chapter12/第十二章 智能体性能评估.md'
    nb_path = '/root/workspace/hello-agents/code/chapter12/第十二章_智能体性能评估.ipynb'
    convert_md_to_notebook(md_path, nb_path)

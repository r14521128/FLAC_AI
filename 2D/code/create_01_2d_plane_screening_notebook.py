from __future__ import annotations

import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent if SCRIPT_DIR.name.lower() == "code" else SCRIPT_DIR
NOTEBOOK_PATH = SCRIPT_DIR / "01_2d_plane_screening.ipynb"
STAGE1_SCRIPT_PATH = SCRIPT_DIR / "stage1_2d_screening.py"


def make_markdown_cell(lines: list[str]) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [line + "\n" for line in lines],
    }


def make_code_cell(code: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in code.strip("\n").splitlines()],
    }


def make_notebook(stage1_code: str) -> dict:
    return {
        "cells": [
            make_markdown_cell(
                [
                    "# 01 Stage 1 2D 無支撐解析解參數篩選",
                    "",
                    "本 notebook 只執行 Stage 1：快速篩選岩體參數與模型合理性。",
                    "",
                    "- 不加入噴凝土。",
                    "- 不加入支護壓力、shell、liner 或 equivalent support。",
                    "- 位移使用 CCM 靜水等效估算，只作快速排序與淘汰，不代表 K0 != 1 的方向性頂拱/側壁解。",
                    "- `score_2d` 只用於快速排序，不代表最終監測校正結果。",
                    "- 通過結果會輸出給 Stage 2 X=12D FLAC3D 小模型讀取。",
                ]
            ),
            make_code_cell(stage1_code),
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "codemirror_mode": {"name": "ipython", "version": 3},
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython3",
                "version": "3.13.5",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> None:
    if not STAGE1_SCRIPT_PATH.exists():
        raise FileNotFoundError(f"找不到 Stage 1 腳本：{STAGE1_SCRIPT_PATH}")

    stage1_code = STAGE1_SCRIPT_PATH.read_text(encoding="utf-8")
    notebook = make_notebook(stage1_code)
    NOTEBOOK_PATH.write_text(
        json.dumps(notebook, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"已更新 notebook：{NOTEBOOK_PATH}")


if __name__ == "__main__":
    main()

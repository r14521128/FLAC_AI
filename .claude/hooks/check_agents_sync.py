#!/usr/bin/env python
# PostToolUse hook: 編輯 CLAUDE.md / AGENTS.md 後，若兩檔內容不一致，
# 注入訊息提示 Claude 詢問使用者是否要執行 align_agents.ps1 對齊。
# 讀 stdin 的 hook JSON，輸出 hookSpecificOutput.additionalContext。
import sys, json, os

ROOT = r"D:\FLAC_AI"
CLAUDE = os.path.join(ROOT, "CLAUDE.md")
AGENTS = os.path.join(ROOT, "AGENTS.md")


def out_nothing():
    sys.exit(0)


try:
    data = json.load(sys.stdin)
except Exception:
    out_nothing()

fp = (data.get("tool_input") or {}).get("file_path", "") or ""
if not fp:
    out_nothing()

# 只在編輯到 root 的 CLAUDE.md 或 AGENTS.md 時才動作
try:
    fp_norm = os.path.normcase(os.path.abspath(fp))
except Exception:
    out_nothing()
targets = {os.path.normcase(CLAUDE), os.path.normcase(AGENTS)}
if fp_norm not in targets:
    out_nothing()

try:
    c = open(CLAUDE, "rb").read()
except Exception:
    out_nothing()
a = open(AGENTS, "rb").read() if os.path.exists(AGENTS) else None

# 已一致 → 不打擾
if a is not None and c == a:
    out_nothing()

msg = (
    "偵測到 CLAUDE.md 與 AGENTS.md 內容不一致（剛編輯了其中一個）。"
    "請用 AskUserQuestion 詢問使用者：是否現在執行 align_agents.ps1 把 CLAUDE.md 對齊到 AGENTS.md"
    "（等同 Copy-Item D:\\FLAC_AI\\CLAUDE.md D:\\FLAC_AI\\AGENTS.md），"
    "或維持現狀、之後（每 2~3 天）再對齊。不要自行決定，先問使用者。"
)
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": msg,
    },
    "systemMessage": "CLAUDE.md 與 AGENTS.md 目前不一致 — Claude 會詢問是否對齊。",
}))

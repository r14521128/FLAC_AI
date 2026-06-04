# -*- coding: utf-8 -*-
"""Create a compact local summary for the Codex daily monitor."""

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "output", "codex_monitor")
DEFAULT_ROOTS = ["AI_交接", "3D_small", "mechanical_properties", "3D_far", "2D"]
DEFAULT_EXTS = [".py", ".ipyn", ".ipynb", ".dat", ".f3dat", ".md", ".txt", ".csv", ".xlsx", ".ps1", ".png"]
SUMMARY_LOG_EXTS = [".log"]
EXCLUDE_DIRS = {".git", "__pycache__", ".ipynb_checkpoints", ".vscode"}
MAX_LIST = 80


def relpath(path):
    return os.path.relpath(path, ROOT).replace("\\", "/")


def file_record(path):
    st = os.stat(path)
    return {
        "path": relpath(path),
        "ext": os.path.splitext(path)[1].lower(),
        "size_mb": round(st.st_size / 1024 / 1024, 3),
        "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
    }


def scan_files(roots, since, allowed_exts):
    since_ts = since.timestamp()
    records = []
    log_records = []
    missing_roots = []

    for root_name in roots:
        root_dir = os.path.join(ROOT, root_name)
        if not os.path.isdir(root_dir):
            missing_roots.append(root_name)
            continue
        for dirpath, dirnames, filenames in os.walk(root_dir):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            for filename in filenames:
                full = os.path.join(dirpath, filename)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                if st.st_mtime < since_ts:
                    continue
                ext = os.path.splitext(filename)[1].lower()
                if ext in allowed_exts:
                    records.append(file_record(full))
                elif ext in SUMMARY_LOG_EXTS:
                    log_records.append(file_record(full))

    records.sort(key=lambda x: (x["mtime"], x["path"]), reverse=True)
    log_records.sort(key=lambda x: (x["mtime"], x["path"]), reverse=True)
    return records, log_records, missing_roots


def summarize_by_root_ext(records):
    counts = Counter()
    for rec in records:
        root = rec["path"].split("/", 1)[0]
        counts[(root, rec["ext"])] += 1
    return [
        {"root": root, "ext": ext, "count": count}
        for (root, ext), count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarize_csv(path):
    try:
        if os.path.getsize(path) > 50 * 1024 * 1024:
            return {"path": relpath(path), "status": "skipped_large_csv"}
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames or []
            rows = list(reader)
    except Exception as exc:
        return {"path": relpath(path), "status": "read_error", "error": str(exc)}

    keys = ["step", "cycle", "ratio", "converged", "crown", "wall", "conv", "plastic"]
    interesting = [field for field in fields if any(key in field.lower() for key in keys)]
    summary = {
        "path": relpath(path),
        "status": "ok",
        "rows": len(rows),
        "columns": fields[:40],
        "interesting_columns": interesting[:30],
    }
    if not rows:
        summary["status"] = "empty"
        return summary

    latest = rows[-1]
    summary["latest"] = {field: latest.get(field, "") for field in interesting[:20]}
    stats = {}
    for field in interesting[:30]:
        values = [safe_float(row.get(field)) for row in rows]
        nums = [value for value in values if value is not None]
        if nums:
            stats[field] = {"min": min(nums), "max": max(nums), "latest": safe_float(latest.get(field))}
    summary["stats"] = stats
    return summary


def summarize_csvs(records):
    csv_records = [rec for rec in records if rec["ext"] == ".csv"]
    summaries = []
    for rec in csv_records[:MAX_LIST]:
        summaries.append(summarize_csv(os.path.join(ROOT, rec["path"].replace("/", os.sep))))
    return summaries


def summarize_ai_handoff(records):
    result = []
    for rec in records:
        if not rec["path"].startswith("AI_交接/") or rec["ext"] != ".md":
            continue
        full = os.path.join(ROOT, rec["path"].replace("/", os.sep))
        headings = []
        bullets = []
        try:
            with open(full, encoding="utf-8-sig", errors="replace") as f:
                for line in f:
                    text = line.strip()
                    if text.startswith("#"):
                        headings.append(text)
                    elif text.startswith("- "):
                        bullets.append(text)
        except OSError:
            continue
        result.append({
            "path": rec["path"],
            "headings": headings[:20],
            "bullets": bullets[:20],
        })
    return result


def build_markdown(data):
    lines = []
    lines.append("# Codex monitor compact summary")
    lines.append("")
    lines.append("## Window")
    lines.append("- since: {}".format(data["since"]))
    lines.append("- until: {}".format(data["until"]))
    lines.append("- roots: {}".format(", ".join(data["roots"])))
    lines.append("")

    if data["missing_roots"]:
        lines.append("## Missing Roots")
        for root in data["missing_roots"]:
            lines.append("- {}".format(root))
        lines.append("")

    lines.append("## Change Counts")
    if data["counts"]:
        for item in data["counts"]:
            lines.append("- {} {}: {}".format(item["root"], item["ext"], item["count"]))
    else:
        lines.append("- no allowed file changes")
    lines.append("")

    lines.append("## Files To Review")
    for rec in data["records"][:MAX_LIST]:
        lines.append("- {path} ({ext}, {size_mb} MB, {mtime})".format(**rec))
    if len(data["records"]) > MAX_LIST:
        lines.append("- ... {} more".format(len(data["records"]) - MAX_LIST))
    lines.append("")

    lines.append("## Log Files Seen But Not Commit Candidates")
    if data["logs"]:
        for rec in data["logs"][:30]:
            lines.append("- {path} ({size_mb} MB, {mtime})".format(**rec))
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## CSV Monitor Summaries")
    for item in data["csv_summaries"][:MAX_LIST]:
        lines.append("- {}".format(item["path"]))
        lines.append("  - status: {}, rows: {}".format(item.get("status"), item.get("rows", "")))
        if item.get("interesting_columns"):
            lines.append("  - columns: {}".format(", ".join(item["interesting_columns"][:12])))
        if item.get("latest"):
            latest = "; ".join("{}={}".format(k, v) for k, v in list(item["latest"].items())[:10])
            lines.append("  - latest: {}".format(latest))
    if not data["csv_summaries"]:
        lines.append("- none")
    lines.append("")

    lines.append("## AI Handoff Notes")
    if data["ai_handoff"]:
        for item in data["ai_handoff"]:
            lines.append("- {}".format(item["path"]))
            for heading in item["headings"][:10]:
                lines.append("  - {}".format(heading))
    else:
        lines.append("- no AI_交接 markdown changes")
    lines.append("")

    lines.append("## PNG Files")
    pngs = [rec for rec in data["records"] if rec["ext"] == ".png"]
    if pngs:
        for rec in pngs[:40]:
            lines.append("- {}".format(rec["path"]))
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--roots", default=",".join(DEFAULT_ROOTS))
    parser.add_argument("--out-dir", default=OUT_DIR)
    args = parser.parse_args()

    roots = [item.strip() for item in args.roots.split(",") if item.strip()]
    now = datetime.now()
    since = now - timedelta(hours=args.hours)
    records, logs, missing_roots = scan_files(roots, since, set(DEFAULT_EXTS))
    data = {
        "since": since.isoformat(timespec="seconds"),
        "until": now.isoformat(timespec="seconds"),
        "roots": roots,
        "allowed_exts": DEFAULT_EXTS,
        "missing_roots": missing_roots,
        "counts": summarize_by_root_ext(records),
        "records": records,
        "logs": logs,
        "csv_summaries": summarize_csvs(records),
        "ai_handoff": summarize_ai_handoff(records),
    }

    os.makedirs(args.out_dir, exist_ok=True)
    latest_json = os.path.join(args.out_dir, "summary_latest.json")
    latest_md = os.path.join(args.out_dir, "summary_latest.md")
    with open(latest_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    with open(latest_md, "w", encoding="utf-8") as f:
        f.write(build_markdown(data))
    print(latest_md)


if __name__ == "__main__":
    main()

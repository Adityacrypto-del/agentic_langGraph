"""Benchmark protocol runner (handbook 11.1): S1x2, S2x3, S3x2, S4x2, S5x1 with --auto-approve.

  python benchmark/protocol.py            # resumes: skips (spec, run) rows already in results.csv

A 2 s pause between runs keeps free-tier providers happy. Real LLM only (never --mock).
"""
import csv
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "benchmark" / "results.csv"
PLAN = [("S1", 2), ("S2", 3), ("S3", 2), ("S4", 2), ("S5", 1)]


def done(sid: str) -> int:
    if not CSV.exists():
        return 0
    return sum(1 for r in csv.DictReader(open(CSV)) if r["platform"] == "langchain" and r["spec"] == sid)


def main():
    first = True
    for sid, n in PLAN:
        for _ in range(n - done(sid)):
            if not first:
                time.sleep(2)
            first = False
            print(f"\n######## protocol: {sid} run {done(sid) + 1}/{n}", flush=True)
            subprocess.run([sys.executable, "-m", "langchain_app.run", f"specs/{sid.lower()}.txt",
                            "--auto-approve"], cwd=ROOT)
    subprocess.run([sys.executable, "benchmark/summary.py"], cwd=ROOT)


if __name__ == "__main__":
    main()

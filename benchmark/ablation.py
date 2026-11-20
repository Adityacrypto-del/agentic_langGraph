"""Ablation (handbook 11.3): does the self-healing loop help?

S2 and S4, 5 runs each, at MAX_RETRIES=0 and MAX_RETRIES=3. Rows go to benchmark/ablation.csv
(same header as results.csv, plus the setting in the platform column, e.g. langchain_r0), so the
main 10-run benchmark stays clean. Resumable.

  python benchmark/ablation.py           # run (resumes)
  python benchmark/ablation.py --summary # print the table only
"""
import csv
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "benchmark" / "ablation.csv"
SPECS, RUNS, SETTINGS = ["S2", "S4"], 5, [0, 3]


def rows():
    return list(csv.DictReader(open(CSV))) if CSV.exists() else []


def summary():
    rs = rows()
    print("| Spec | MAX_RETRIES | Success | Avg retries | Avg seconds |")
    print("|---|---|---|---|---|")
    for s in SPECS:
        for m in SETTINGS:
            sel = [r for r in rs if r["spec"] == s and r["platform"] == f"langchain_r{m}"]
            if not sel:
                print(f"| {s} | {m} | _TBD_ | | |")
                continue
            n = len(sel); ok = sum(int(r["success"]) for r in sel)
            print(f"| {s} | {m} | {ok}/{n} | {sum(float(r['retries']) for r in sel)/n:.2f} | "
                  f"{sum(float(r['seconds']) for r in sel)/n:.0f} |")


def main():
    if "--summary" in sys.argv:
        return summary()
    for m in SETTINGS:
        for s in SPECS:
            have = sum(1 for r in rows() if r["spec"] == s and r["platform"] == f"langchain_r{m}")
            for k in range(have, RUNS):
                print(f"\n######## ablation: {s} MAX_RETRIES={m} run {k + 1}/{RUNS}", flush=True)
                tmp = ROOT / "benchmark" / ".ablation_tmp.csv"
                tmp.unlink(missing_ok=True)
                subprocess.run([sys.executable, "-m", "langchain_app.run", f"specs/{s.lower()}.txt",
                                "--auto-approve", "--max-retries", str(m), "--csv", str(tmp)], cwd=ROOT)
                if tmp.exists():
                    r = list(csv.DictReader(open(tmp)))[-1]
                    r["platform"], r["run"] = f"langchain_r{m}", str(k + 1)
                    new = not CSV.exists()
                    with open(CSV, "a", newline="") as f:
                        w = csv.DictWriter(f, fieldnames=list(r.keys()))
                        if new:
                            w.writeheader()
                        w.writerow(r)
                    tmp.unlink()
                time.sleep(2)
    summary()


if __name__ == "__main__":
    main()

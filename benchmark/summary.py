"""Benchmark summary (handbook 11.2, verbatim logic) + a per-spec breakdown.

  python benchmark/summary.py [benchmark/results.csv]
"""
import collections
import csv
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "benchmark/results.csv"
rows = list(csv.DictReader(open(path)))
by = collections.defaultdict(list)
for r in rows: by[r["platform"]].append(r)
for p, rs in by.items():
    n = len(rs); ok = sum(int(r["success"]) for r in rs)
    print(f"{p:10s} success {ok}/{n}  avg retries {sum(float(r['retries'] or 0) for r in rs)/n:.2f}"
          f"  avg time {sum(float(r['seconds'] or 0) for r in rs)/n:.0f}s")

# per-spec breakdown (extra, same data)
print("\nper spec:")
spec = collections.defaultdict(list)
for r in rows: spec[(r["platform"], r["spec"])].append(r)
for (p, s), rs in sorted(spec.items()):
    n = len(rs); ok = sum(int(r["success"]) for r in rs)
    print(f"  {p:10s} {s}: success {ok}/{n}  avg retries {sum(float(r['retries'] or 0) for r in rs)/n:.2f}"
          f"  avg time {sum(float(r['seconds'] or 0) for r in rs)/n:.0f}s")

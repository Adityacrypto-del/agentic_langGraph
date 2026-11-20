"""CLI for FrostByte (LangChain edition).

  python -m langchain_app.run specs/s2.txt [--auto-approve] [--mock] [--max-retries N]
                                           [--runs K] [--diagram] [--csv PATH]

Writes outputs/<module_name>/{design.v, tb.v, report.md, metrics.json, trace.jsonl, tools.json}
(mock runs go to outputs/mock_<module_name>/) and appends one row per real run to
benchmark/results.csv. Mock runs are NEVER written to the benchmark.
"""
import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from .llm import get_llm, model_label  # noqa: E402
from .pipeline import build_pipeline  # noqa: E402
from .tracing import MOCK_LABEL, FrostByteTracer  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CSV_HEADER = ["platform", "spec", "run", "success", "retries", "seconds", "cells", "power_nw",
              "failure_reason"]


def spec_id(path: str) -> str:
    m = re.search(r"s(\d+)", Path(path).stem, re.I)
    return f"S{m.group(1)}" if m else Path(path).stem


def next_run_number(csv_path: Path, sid: str) -> int:
    if not csv_path.exists():
        return 1
    rows = list(csv.DictReader(open(csv_path)))
    return 1 + sum(1 for r in rows if r["platform"] == "langchain" and r["spec"] == sid)


def append_csv(csv_path: Path, row: dict) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    new = not csv_path.exists() or csv_path.stat().st_size == 0
    with open(csv_path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADER)
        if new:
            w.writeheader()
        w.writerow(row)


def run_once(spec_path: str, args) -> dict:
    sid = spec_id(spec_path)
    request = open(spec_path).read()
    tracer = FrostByteTracer(mock=args.mock)
    pipe = build_pipeline(get_llm(args.mock), max_retries=args.max_retries,
                          auto_approve=args.auto_approve)
    print(f"\n=== FrostByte (LangChain) | {sid} | model {model_label(args.mock)} | "
          f"MAX_RETRIES={args.max_retries} ===")
    t0 = time.time()
    state, error = None, None
    try:
        state = pipe.invoke({"request": request}, {"callbacks": [tracer], "run_name": "frostbyte"})
    except Exception as e:                       # report crashes honestly (e.g. rate limits)
        error = f"{type(e).__name__}: {e}"
        print(f"\nRUN CRASHED: {error[:300]}")
    seconds = round(time.time() - t0, 1)

    clarified = bool(state and state.get("status") == "clarification")
    passed = bool(state and state.get("passed"))
    syn = (state or {}).get("synth") or {}
    pwr = (state or {}).get("pwr") or {}
    synth_ok = bool(syn.get("ok"))

    # ---- success rules (handbook 11.1)
    if sid == "S5":
        success = clarified
        reason = "" if success else (error or "did not ask clarification questions")
    else:
        success = passed and synth_ok
        if error:
            reason = error
        elif clarified:
            reason = "asked clarification questions on a complete spec"
        elif not passed:
            last = (state.get("history") or ["no retries"])[-1]
            reason = f"sim failed after {state.get('retries')} retries; last: {last}"
        elif not synth_ok:
            reason = "synthesis failed"
        else:
            reason = ""

    # ---- outputs
    spec = (state or {}).get("spec") or {}
    if clarified:
        print("\nCLARIFICATION NEEDED:")
        for q in state.get("questions") or []:
            print(" -", q)
        name = f"clarification_{Path(spec_path).stem}"
    else:
        name = spec.get("module_name") or f"failed_{Path(spec_path).stem}"
    if args.mock:
        name = "mock_" + name
    out = ROOT / "outputs" / name
    out.mkdir(parents=True, exist_ok=True)

    if state and not clarified:
        (out / "design.v").write_text(state.get("rtl", ""))
        (out / "tb.v").write_text(state.get("tb", ""))
        if state.get("report"):
            report = state["report"]
            if args.mock and MOCK_LABEL not in report:
                report = f"> **{MOCK_LABEL}**\n\n" + report
            (out / "report.md").write_text(report)
        sim = state.get("sim") or {}
        tools = {"sim": {k: v for k, v in sim.items() if k != "ctx"},
                 "synth": {k: v for k, v in syn.items() if k != "ctx"},
                 "power": {k: v for k, v in pwr.items() if k != "ctx"},
                 "agent_steps": state.get("agent_steps"), "history": state.get("history")}
        (out / "tools.json").write_text(json.dumps(tools, indent=1))
        (out / "spec.json").write_text(json.dumps(spec, indent=1))
    if clarified:
        (out / "questions.json").write_text(json.dumps(state.get("questions"), indent=1))

    metrics = {
        "spec": sid, "model": model_label(args.mock), "mock": args.mock,
        "ok": success, "retries": (state or {}).get("retries", 0), "seconds": seconds,
        "cells": syn.get("cells"), "dffs": syn.get("dffs"), "area_ge": syn.get("area_ge"),
        "power_nw": pwr.get("dynamic_nw"), "within_budget": pwr.get("within_budget"),
        "budget_nw": pwr.get("budget_nw"),
        "sim_total": ((state or {}).get("sim") or {}).get("total"),
        "sim_failed": ((state or {}).get("sim") or {}).get("failed"),
        "llm_calls": tracer.llm_calls, "tokens": tracer.tokens,
        "lint_calls": (state or {}).get("lint_calls", 0),
        "verify_lints": (state or {}).get("verify_lints", 0),
        "history": (state or {}).get("history", []),
        "approved_by": (state or {}).get("approved_by"),
        "clarification": clarified, "failure_reason": reason,
    }
    if args.mock:
        metrics["label"] = MOCK_LABEL
    (out / "metrics.json").write_text(json.dumps(metrics, indent=1))
    tracer.write_jsonl(str(out / "trace.jsonl"))

    print(f"\nRESULT {sid}: success={int(success)} retries={metrics['retries']} seconds={seconds} "
          f"cells={metrics['cells']} dffs={metrics['dffs']} area_ge={metrics['area_ge']} "
          f"power_nw={metrics['power_nw']} llm_calls={tracer.llm_calls} -> {out.relative_to(ROOT)}")
    if args.mock:
        print(f"*** {MOCK_LABEL} — not written to the benchmark ***")
    else:
        csv_path = Path(args.csv)
        append_csv(csv_path, {
            "platform": "langchain", "spec": sid, "run": next_run_number(csv_path, sid),
            "success": int(success), "retries": metrics["retries"], "seconds": seconds,
            "cells": metrics["cells"] if metrics["cells"] is not None else "",
            "power_nw": metrics["power_nw"] if metrics["power_nw"] is not None else "",
            "failure_reason": reason[:200]})
    return metrics


def main(argv=None):
    ap = argparse.ArgumentParser(description="FrostByte, LangChain edition")
    ap.add_argument("spec", help="path to a spec file, e.g. specs/s2.txt")
    ap.add_argument("--auto-approve", action="store_true", help="skip the human approval prompt")
    ap.add_argument("--mock", action="store_true", help="scripted offline LLM (S1, S5 only)")
    ap.add_argument("--max-retries", type=int, default=int(os.getenv("MAX_RETRIES", "3")))
    ap.add_argument("--runs", type=int, default=1, help="repeat the run K times")
    ap.add_argument("--diagram", action="store_true", help="print the LCEL graph as Mermaid and exit")
    ap.add_argument("--csv", default=str(ROOT / "benchmark" / "results.csv"),
                    help="benchmark CSV to append to (real runs only)")
    args = ap.parse_args(argv)

    if args.diagram:
        print(build_pipeline(get_llm(mock=True)).get_graph().draw_mermaid())
        return
    results = []
    for k in range(args.runs):
        if k and not args.mock:
            time.sleep(2)                        # free-tier friendliness between runs
        results.append(run_once(args.spec, args))
    return results


if __name__ == "__main__":
    main()
    sys.exit(0)

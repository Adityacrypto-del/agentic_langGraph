"""FrostByte shared EDA tool server (handbook Section 5, verbatim + GET /health).

Shared by every platform (LangChain, LangGraph, n8n, CrewAI, Dify).
Agentic AI concept: these are the TOOLS the agents act through.
"""
import re, subprocess, uuid
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="FrostByte EDA Tools", version="1.0")
RUNS = Path("/tmp/frostbyte_runs"); RUNS.mkdir(parents=True, exist_ok=True)

def run(cmd, cwd, timeout=60):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout + p.stderr
    except FileNotFoundError:
        raise HTTPException(500, f"{cmd[0]} is not installed in the tool server")
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s (infinite loop? missing $finish?)"

@app.get("/health")
def health():
    return {"ok": True}

def new_run():
    rid = uuid.uuid4().hex[:8]
    d = RUNS / rid; d.mkdir()
    return rid, d

class LintReq(BaseModel):
    design_code: str
    ctx: Optional[dict] = None

class SimReq(BaseModel):
    design_code: str
    tb_code: str
    ctx: Optional[dict] = None

class SynthReq(BaseModel):
    design_code: str
    top: str
    ctx: Optional[dict] = None

class PowerReq(BaseModel):
    run_id: str
    clk_hz: float = 32768
    vdd: float = 1.2
    cap_ff: float = 5.0          # assumed switched capacitance per net toggle
    tb_clk_ns: float = 10.0      # testbench clock period
    budget_nw: Optional[float] = None
    ctx: Optional[dict] = None

@app.post("/lint")
def lint(r: LintReq):
    rid, d = new_run()
    (d / "design.v").write_text(r.design_code)
    rc, out = run(["iverilog", "-g2012", "-Wall", "-o", "design.vvp", "design.v"], d)
    return {"ok": rc == 0, "log": out[-3000:], "ctx": r.ctx}

@app.post("/simulate")
def simulate(r: SimReq):
    rid, d = new_run()
    (d / "design.v").write_text(r.design_code)
    (d / "tb.v").write_text(r.tb_code)
    rc, out = run(["iverilog", "-g2012", "-Wall", "-o", "sim.vvp", "design.v", "tb.v"], d)
    if rc != 0:
        return {"passed": False, "stage": "compile", "run_id": rid, "total": 0,
                "failed": 0, "log": out[-3000:], "ctx": r.ctx}
    rc, out = run(["vvp", "sim.vvp"], d, timeout=30)
    m = re.search(r"TEST_RESULT:\s*(PASS|FAIL)", out)
    c = re.search(r"total=(\d+)\s+failed=(\d+)", out)
    total, failed = (int(c.group(1)), int(c.group(2))) if c else (0, 0)
    passed = bool(m and m.group(1) == "PASS" and rc == 0 and total > 0)  # total>0 blocks vacuous passes
    return {"passed": passed, "stage": "run", "run_id": rid, "total": total,
            "failed": failed, "log": out[-3000:], "ctx": r.ctx}

# Rough generic gate-equivalents (NAND2 = 1). An ESTIMATE, not a layout area.
GE = {"$_NOT_": 0.5, "$_NAND_": 1, "$_NOR_": 1, "$_AND_": 1.5, "$_OR_": 1.5,
      "$_ANDNOT_": 1.5, "$_ORNOT_": 1.5, "$_XOR_": 2.5, "$_XNOR_": 2.5, "$_MUX_": 2.5}

@app.post("/synthesize")
def synthesize(r: SynthReq):
    rid, d = new_run()
    (d / "design.v").write_text(r.design_code)
    script = (f"read_verilog -sv design.v; hierarchy -check -top {r.top}; "
              f"synth -flatten -top {r.top}; stat")
    rc, out = run(["yosys", "-p", script], d, timeout=90)
    if rc != 0:
        return {"ok": False, "log": out[-3000:], "ctx": r.ctx}
    stat = out.split("Printing statistics")[-1]
    cells = {}
    for line in stat.splitlines():     # handles both old and new Yosys 'stat' layouts
        m = (re.match(r"^\s*(\$\S+)\s+(\d+)\s*$", line))
        if m: cells[m.group(1)] = int(m.group(2)); continue
        m = re.match(r"^\s*(\d+)\s+(?:[\d.eE+]+\s+)?(\$\S+)\s*$", line)
        if m: cells[m.group(2)] = int(m.group(1))
    dffs = sum(n for k, n in cells.items() if "DFF" in k)
    area = sum(n * (5 if "DFF" in k else 3.5 if "LATCH" in k else GE.get(k, 1.5))
               for k, n in cells.items())
    return {"ok": True, "top": r.top, "cells": sum(cells.values()), "dffs": dffs,
            "breakdown": cells, "area_ge": round(area, 1), "log": stat[-1500:], "ctx": r.ctx}

def _flips(prev, new):
    if prev is None or set(prev + new) & set("xXzZ"):
        return 0
    n = max(len(prev), len(new))
    return sum(a != b for a, b in zip(prev.rjust(n, "0"), new.rjust(n, "0")))

def parse_vcd(path):
    text = Path(path).read_text()
    m = re.search(r"\$timescale\s+(\d+)\s*(fs|ps|ns|us|ms|s)\s+\$end", text)
    to_ns = {"fs": 1e-6, "ps": 1e-3, "ns": 1.0, "us": 1e3, "ms": 1e6, "s": 1e9}
    ts_ns = int(m.group(1)) * to_ns[m.group(2)] if m else 1.0
    scope, dut_ids, last, toggles, t = [], set(), {}, 0, 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line: continue
        if line.startswith("$scope"): scope.append(line.split()[2])
        elif line.startswith("$upscope"): scope.pop()
        elif line.startswith("$var"):
            if "dut" in scope: dut_ids.add(line.split()[3])   # TB must name the instance 'dut'
        elif line[0] == "#": t = int(line[1:])
        elif line[0] in "01xXzZ":
            val, vid = line[0], line[1:]
            if vid in dut_ids: toggles += _flips(last.get(vid), val)
            last[vid] = val
        elif line[0] in "bB":
            val, vid = line[1:].split()
            if vid in dut_ids: toggles += _flips(last.get(vid), val)
            last[vid] = val
    return toggles, t * ts_ns

@app.post("/power")
def power(r: PowerReq):
    vcd = RUNS / r.run_id / "wave.vcd"
    if not vcd.exists():
        return {"ok": False, "log": "wave.vcd not found: the testbench must call $dumpfile(\"wave.vcd\")", "ctx": r.ctx}
    toggles, sim_ns = parse_vcd(vcd)
    cycles = max(sim_ns / r.tb_clk_ns, 1)
    per_cycle = toggles / cycles
    e_cycle = per_cycle * 0.5 * (r.cap_ff * 1e-15) * r.vdd ** 2
    nw = e_cycle * r.clk_hz * 1e9
    return {"ok": True, "toggles": toggles, "cycles": round(cycles),
            "toggles_per_cycle": round(per_cycle, 3), "dynamic_nw": round(nw, 4),
            "budget_nw": r.budget_nw,
            "within_budget": None if r.budget_nw is None else nw <= r.budget_nw,
            "assumptions": f"E=0.5*C*V^2 per net toggle, C={r.cap_ff} fF, V={r.vdd} V, f={r.clk_hz} Hz; "
                           "stimulus is accelerated so this is a conservative relative index, not silicon-accurate; "
                           "leakage and clock-tree power excluded",
            "ctx": r.ctx}

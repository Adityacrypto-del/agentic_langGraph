# FrostByte: Policy-to-Silicon Agents for Vaccine Cold-Chain Chips
Implementation handbook for a 4-member team: LangGraph · n8n · CrewAI · Dify
## 0. How to use this handbook
Whole team together (Days 1-2): Sections 1-6. These are shared: the SDG reasoning, the shared tool server, the shared prompts and the five test specs.
Each member alone (Days 3-6): your own platform section (7 LangGraph, 8 n8n, 9 CrewAI, 10 Dify). If you are only 3 people, drop Dify.
Whole team together (Days 7-8): Sections 11-12 (benchmark and posters).
Section 13 has copy-paste prompts for using Claude as your coding partner. Section 14 lists the errors you will hit and how to fix them.
Honesty rule: every number on a poster (cell count, pass rate, retries, time) must come from your own run. This handbook never gives you fake results. It tells you what to measure.
Tested assumptions: Python 3.11, Docker Desktop or Docker Engine, Ubuntu or Windows with WSL2. Library versions change quickly, so after everything works run pip freeze > requirements.lock and commit it.

## 1. SDG-first: how we chose the topic
Most teams pick a project and then force an SDG logo onto it. We did the reverse, in five steps:
List all 17 SDGs and pick the ones with a concrete, local, measurable problem (not just a slogan).
For each, write the real-world problem in one sentence.
Ask: is there a digital-hardware bottleneck where a small custom chip is the right tool? (This is the VLSI link.)
Ask: can we show results in simulation with free tools?
Ask: will 50 other teams also build this? Score and pick.
### Scorecard (score each 1-5; this is our judgement, argue with it and re-score as a team)
| # | SDG and target | Real problem | VLSI bottleneck? | Simulatable? | Unique? | Total /15 |
| 1 | SDG 3, target 3.8 (access to safe, effective, affordable essential vaccines) | Vaccines are damaged when the cold chain breaks (heat or accidental freezing) and the damage is invisible | 5: a tiny always-on, ultra-low-power policy chip | 5: temperature traces are easy to simulate | 4 | 14 |
| 2 | SDG 7, target 7.3 (energy efficiency) | Smart-meter power optimisation | 3 | 4 | 2 | 9 |
| 3 | SDG 2, target 2.3 (smallholder farmers) | Irrigation controller | 3 | 4 | 2 | 9 |
| 4 | SDG 6, target 6.1 (safe drinking water) | Water-quality sensor node | 3 | 3 | 3 | 9 |
| 5 | SDG 11, target 11.5 (disaster resilience) | Early-warning node | 3 | 2 | 3 | 8 |
| 6 | SDG 4, target 4.4 (skills) | A VLSI tutor chatbot | 2 | 4 | 1 | 7 |
Winner: SDG 3 (vaccine cold chain). The project then follows from the SDG, not the other way round.
### SDG mapping (state it modestly: "supports", never "solves")
| SDG | How FrostByte supports it |
| SDG 3: Good Health and Well-being (primary, target 3.8) | Makes it faster and cheaper to design the tiny monitor chips that watch vaccine storage temperature, so vaccines stay potent from factory to clinic |
| SDG 9: Industry, Innovation and Infrastructure (target 9.5, upgrading technological capabilities) | Lowers the barrier to custom chip design: a public-health rule goes in, verified RTL and synthesis numbers come out, using only open-source tools |
| SDG 4: Quality Education (target 4.4, technical skills) | Every run produces a readable log of what failed and why, so students learn RTL by watching the self-debugging loop |
Evidence to cite on your poster: look up WHO vaccine storage and handling guidance, WHO PQS (Performance, Quality and Safety) specifications for temperature monitoring devices, and UNICEF Supply Division material. Cite them yourselves. Do not copy statistics from this handbook, because it contains none.

## 2. Project overview
### One-line pitch
FrostByte is an agent crew that turns a vaccine-storage rule written in plain English into verified, synthesized Verilog for a battery-powered temperature-excursion monitor chip, and proves it with a real compiler, a real simulator, a real synthesizer and a switching-activity power estimate.
### Why this is unique (even if everyone else also uses AI)
Anyone can paste "write a UART" into a chatbot. FrostByte differs in ways judges can verify:
Policy to silicon. The input is a public-health rule, not a textbook circuit.
Spec-derived testbenches. The testbench is generated from the spec, never from the RTL, so it cannot just mirror a bug. The spec analyst writes the test scenarios first.
Culprit classification. On failure, the debugger must decide whether the RTL or the testbench is wrong, judged only against the spec. Most demos blame the RTL every time.
Clarification gate. An ambiguous request ("warn me when it gets too warm") makes the crew ask questions instead of guessing.
Power-budget gate. A VCD-based switching-activity estimate tells you whether the design fits a coin-cell power budget.
One use case, four frameworks, measured. Same tools, same prompts, same five specs, with a benchmark table.
### Temperature encoding used everywhere
Signed 8-bit two's complement, 0.5 °C per LSB. So 0 °C = 0, 2 °C = 4, 8 °C = 16, -1 °C = -2. The monitored range is 2-8 °C (typical for vaccine storage). Freezing (0 °C or below) is treated as the most severe event because freeze-sensitive vaccines can be permanently damaged.
### The pipeline (identical on all platforms)
User request
   |
   v
[1 Spec Analyst] --needs_clarification--> ask user questions, STOP
   | spec JSON (ports, rules, test scenarios, power budget)
   v
[2 RTL Designer] --> design.v
   v
[3 /lint (iverilog)] --errors--> [Debugger] --+
   | ok                                        |
   v                                           |
[4 Testbench Writer] (from SPEC only)          |
   v                                           |
[5 /simulate (iverilog + vvp)] --FAIL--> [Debugger] (max 3 retries)
   | PASS                                      |
   v                                           |
[6 /synthesize (Yosys)] cells, DFFs, area (gate-equivalents)
   v
[7 /power (VCD toggles)] nW estimate vs budget
   v
[8 Human approval] --> [9 Report: code + logs + numbers]
### The five test specs (the "design family")
| ID | Name | Difficulty | What it tests |
| S1 | Excursion debouncer | Easy | Counters, signed comparison, saturation |
| S2 | Freeze/heat alarm FSM with latch (headline demo) | Medium | 4-state FSM, priority rules, latched alarm, acknowledge |
| S3 | Min/max temperature logger | Medium | Signed compare traps, sync clear |
| S4 | Heat-dose integrator (like a Vaccine Vial Monitor) | Hard | Width/overflow, saturating arithmetic, threshold |
| S5 | Ambiguous request | n/a | Must trigger the clarification gate |
Stretch ideas if you finish early: a 10-minute sample-tick prescaler from a 32.768 kHz clock; an SPI-lite readout port; swapping Yosys generic gates for a real open cell library (Sky130) to get real area.

## 3. Beginner glossary
| Term | Meaning |
| LLM | The language model (Groq, Gemini or Ollama) that writes text and code |
| Agent | An LLM given a role, instructions and optionally tools |
| Tool | A function the agent or workflow can call (here: lint, simulate, synthesize, power) |
| Orchestration | The logic deciding who runs when, including loops and branches. This is the only thing that differs between platforms |
| RTL | Register-Transfer Level: the Verilog describing the chip's logic |
| Testbench | Verilog that drives inputs into the design and checks outputs |
| Lint/compile | Check the code is syntactically valid (iverilog) |
| Synthesis | Turn RTL into gates (Yosys). Gives the cell count and area |
| VCD | Value Change Dump: the waveform file a simulation writes |
| Async active-low reset | rst_n=0 immediately forces the design to its start state, with no clock needed |
| State (LangGraph) | A shared dictionary every node reads and updates |

## 4. Setup
### 4.1 Repository layout
frostbyte/
├─ docker-compose.yml
├─ .env
├─ tools/            Dockerfile  requirements.txt  server.py  smoke.py
├─ common/           prompts.py  utils.py  tools_client.py
├─ specs/            s1.txt  s2.txt  s3.txt  s4.txt  s5.txt
├─ langgraph_app/    run.py
├─ crewai_app/       run.py
├─ benchmark/        results.csv
└─ outputs/          generated design.v, tb.v, reports
### 4.2 Install
# Docker route (recommended: works the same on every laptop)
docker compose up --build -d
curl http://localhost:8000/docs      # opens the FastAPI test page in a browser too

# Native route (Ubuntu / WSL2)
sudo apt update && sudo apt install -y iverilog yosys gtkwave python3-venv
Use a separate virtual environment per framework. LangGraph, CrewAI and Dify tooling pin conflicting dependency versions.
python3 -m venv .venv-lg && source .venv-lg/bin/activate
pip install langgraph langchain-core langchain-groq requests python-dotenv
### 4.3 .env (never commit this; add it to .gitignore)
GROQ_API_KEY=your_key_here
LLM_MODEL=llama-3.3-70b-versatile
EDA_URL=http://localhost:8000
Model names on free tiers change. Open the Groq (or Google AI Studio) model list and put a currently available, code-capable model in LLM_MODEL. Free-tier rate limits are real: add a 2-second pause between agent calls or ask Claude for a retry-with-backoff wrapper (Section 13). Local alternative: install Ollama and use a coder model, with no limits but slower.
### 4.4 docker-compose.yml
services:
  eda:
    build: ./tools
    ports: ["8000:8000"]
  n8n:
    image: n8nio/n8n
    ports: ["5678:5678"]
    environment:
      - GENERIC_TIMEZONE=Asia/Kolkata
    volumes:
      - n8n_data:/home/node/.n8n
volumes:
  n8n_data:
Inside n8n, the tool server is reachable at http://eda:8000. From your laptop it is http://localhost:8000. Mixing these up is the number one n8n error.
### 4.5 tools/Dockerfile and tools/requirements.txt
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends iverilog yosys && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]

fastapi
uvicorn
pydantic

## 5. The shared tool server (tools/server.py)
Four endpoints: /lint, /simulate, /synthesize, /power. Every request accepts an optional ctx dictionary that is echoed back unchanged. This is a deliberate trick: workflow tools like n8n and Dify lose data between nodes, and ctx lets the whole workflow state travel through each tool call.
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
Be honest about the power number on the poster: it is a switching-activity estimate (a relative index good for comparing two RTL versions), not a measured chip power. Say so. Judges respect that.
### Smoke test (tools/smoke.py): run this before any LLM is involved
import requests, os
U = os.getenv("EDA_URL", "http://localhost:8000")
D = """module cnt(input clk, input rst_n, output reg [3:0] q);
always @(posedge clk or negedge rst_n) if (!rst_n) q <= 0; else q <= q + 1;
endmodule"""
TB = """`timescale 1ns/1ps
module tb; reg clk=0, rst_n=0; wire [3:0] q; integer total=0, failed=0;
cnt dut(.clk(clk), .rst_n(rst_n), .q(q));
always #5 clk = ~clk;
initial begin
  $dumpfile("wave.vcd"); $dumpvars(0, tb);
  #12 rst_n = 1; repeat (3) @(posedge clk); #1;
  total = total + 1; if (q !== 4'd3) failed = failed + 1;
  if (failed == 0) $display("TEST_RESULT: PASS total=%0d failed=%0d", total, failed);
  else $display("TEST_RESULT: FAIL total=%0d failed=%0d", total, failed);
  $finish;
end endmodule"""
print(requests.post(U + "/lint", json={"design_code": D}).json())
s = requests.post(U + "/simulate", json={"design_code": D, "tb_code": TB}).json(); print(s)
print(requests.post(U + "/synthesize", json={"design_code": D, "top": "cnt"}).json())
print(requests.post(U + "/power", json={"run_id": s["run_id"], "budget_nw": 100}).json())
Expected: lint ok: true; simulate passed: true, total: 1; synthesize returns a non-zero cells and dffs: 4; power returns ok: true. If all four work, the foundation is solid. If not, fix this before touching any agent code.

## 6. Shared prompts, helpers and the five specs
Everyone uses exactly these prompts, so the comparison across platforms is fair. n8n and Dify members copy-paste them into the node settings.
### 6.1 common/utils.py
import json, re

def extract_code(text: str) -> str:
    m = re.search(r"```(?:verilog|systemverilog|sv|v)?\s*\n(.*?)```", text, re.S | re.I)
    return (m.group(1) if m else text).strip() + "\n"

def extract_json(text: str) -> dict:
    t = re.sub(r"```(?:json)?", "", text)
    a, b = t.find("{"), t.rfind("}")
    return json.loads(t[a:b + 1])
### 6.2 common/tools_client.py
import os, requests
BASE = os.getenv("EDA_URL", "http://localhost:8000")

def _post(path, payload):
    r = requests.post(BASE + path, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()

def lint(rtl):               return _post("/lint", {"design_code": rtl})
def simulate(rtl, tb):       return _post("/simulate", {"design_code": rtl, "tb_code": tb})
def synthesize(rtl, top):    return _post("/synthesize", {"design_code": rtl, "top": top})
def power(run_id, clk_hz=32768, budget_nw=None):
    return _post("/power", {"run_id": run_id, "clk_hz": clk_hz, "budget_nw": budget_nw})
### 6.3 common/prompts.py
SPEC_SYSTEM = """You are a hardware specification analyst for ultra-low-power vaccine cold-chain monitor chips.
Convert the user's request into ONE JSON object. Output the JSON only: no markdown fences, no commentary.

CLARIFICATION GATE: set "needs_clarification": true and put 2-4 precise questions in "questions" if ANY of
these is not stated or clearly implied: temperature encoding/units, numeric thresholds, how many samples or
how long before alarming, whether the alarm latches or clears, reset/clear behaviour. Never invent them.
If true, the other fields may be empty.

Otherwise fill this schema:
{
 "needs_clarification": false, "questions": [],
 "module_name": "snake_case",
 "summary": "one sentence",
 "parameters": [{"name":"N","default":3,"meaning":"..."}],
 "ports": [{"name":"clk","dir":"input","width":1,"meaning":"..."}],
 "reset": {"name":"rst_n","kind":"async","active":"low"},
 "rules": ["numbered, cycle-accurate, unambiguous statements"],
 "test_scenarios": [{"name":"...","inputs":"exact per-cycle input sequence","expected":"exact output values visible after the posedge that samples those inputs"}],
 "clk_hz": 32768,
 "power_budget_nw": 100
}
Rules: one clock domain; list every port; clk_hz and power_budget_nw default to 32768 and 100 if not given;
write at least 10 test scenarios covering reset, exact boundaries (at threshold, one above, one below) and
back-to-back samples; every scenario must be derivable from the rules alone, never from an implementation."""

RTL_SYSTEM = """You are an expert RTL designer. Write synthesizable Verilog-2005 implementing the SPEC JSON exactly.
- Exactly one module, using the spec's module_name and ports; use `parameter` for spec parameters.
- Sequential logic: always @(posedge clk or negedge rst_n) with non-blocking (<=) assignments, matching the spec's reset kind.
- Combinational logic: always @* with blocking (=) and a default value for every output (no latches).
- No initial blocks, no # delays, no $display, no tri-state, no real numbers.
- Use `reg signed`/`wire signed`/$signed() explicitly whenever signed values are compared or added.
- Output ONLY one ```verilog code block. No commentary."""

TB_SYSTEM = """You are a verification engineer. Write ONE self-checking Verilog testbench from the SPEC JSON only.
You have NOT seen the RTL; test the spec's rules and test_scenarios, not an implementation.
Mandatory rules:
- `timescale 1ns/1ps; top module named tb; DUT instance must be named exactly `dut`; 10 ns clock.
- Drive inputs on negedge clk. Check outputs 1 ns after the posedge that samples those inputs.
- Use the check task from the skeleton for every comparison. Use !== so X values fail.
- Call $dumpfile("wave.vcd"); $dumpvars(0, tb); at time zero.
- The final lines must print exactly: TEST_RESULT: PASS total=<n> failed=<m>  (or FAIL), then $finish.
- Include the timeout watchdog from the skeleton.
Skeleton:
`timescale 1ns/1ps
module tb;
  integer total = 0, failed = 0;
  reg clk = 0;  // plus the DUT's input regs and output wires
  always #5 clk = ~clk;
  task check(input [63:0] exp, input [63:0] act, input [255:0] label);
    begin
      total = total + 1;
      if (exp !== act) begin
        failed = failed + 1;
        $display("FAIL: %0s exp=%0d act=%0d t=%0t", label, exp, act, $time);
      end
    end
  endtask
  // <DUT instance named dut, stimulus, checks>
  initial begin
    $dumpfile("wave.vcd"); $dumpvars(0, tb);
    // ... reset, stimulus, check(...) calls ...
    if (failed == 0) $display("TEST_RESULT: PASS total=%0d failed=%0d", total, failed);
    else $display("TEST_RESULT: FAIL total=%0d failed=%0d", total, failed);
    $finish;
  end
  initial begin #2000000; $display("TEST_RESULT: FAIL total=0 failed=1 timeout"); $finish; end
endmodule
Output ONLY one ```verilog code block. No commentary."""

DEBUG_SYSTEM = """You are a debugging engineer. You receive SPEC, the current RTL, the current TESTBENCH and a failing
tool LOG (compiler error or simulation failures).
1. Decide who is wrong, judging ONLY against the SPEC: the RTL or the TESTBENCH.
2. Your first line must be exactly `CULPRIT: RTL` or `CULPRIT: TB`.
3. Then one sentence of diagnosis, then the COMPLETE corrected file in one ```verilog block.
Keep module name, ports and the TEST_RESULT print format unchanged. Never weaken or delete checks to make tests pass."""

REPORT_SYSTEM = """You write a concise engineering report in markdown from a JSON bundle. Sections: Summary, Spec rules,
Design decisions, Verification result, Synthesis result, Power estimate (state it is a switching-activity estimate),
Retry history, Limitations. Use ONLY numbers present in the bundle. Never invent results."""
### 6.4 The five specs (save each as specs/sN.txt; use the same files on every platform)
S1: Excursion debouncer (easy)
Design a vaccine-fridge excursion alarm. Inputs: clk; rst_n (active-low asynchronous reset); sample_valid (1-bit strobe, high for one cycle when a new reading arrives); temp (signed 8-bit two's complement, 0.5 degC per LSB). A reading is out-of-range if temp < 4 (below 2 degC) or temp > 16 (above 8 degC). Readings are evaluated only in cycles where sample_valid=1. Count consecutive out-of-range readings; an in-range reading resets the count to 0; the count saturates at 3. Output alarm=1 whenever the count equals 3, otherwise 0. Sampling clock is 32768 Hz.
S2: Freeze/heat alarm FSM with latch (headline demo)
Design a vaccine-fridge alarm FSM. Inputs: clk; rst_n (active-low asynchronous reset); sample_valid (1-bit strobe); temp (signed 8-bit two's complement, 0.5 degC per LSB); ack (1-bit, an operator acknowledge, may be high in any cycle). Outputs: alarm (1 bit), state (2 bits), bad_count (4 bits). States: NORMAL=0, SUSPECT=1, ALARM_EXCURSION=2, ALARM_FREEZE=3. A reading is bad if temp < 4 or temp > 16. A reading is freezing if temp <= 0. Readings are evaluated only when sample_valid=1. From NORMAL: a freezing reading goes to ALARM_FREEZE; else a bad reading goes to SUSPECT with bad_count=1; else stay. From SUSPECT: a freezing reading goes to ALARM_FREEZE; a bad reading increments bad_count and, when bad_count reaches 3, goes to ALARM_EXCURSION; an in-range reading goes to NORMAL with bad_count=0. In either ALARM state, readings are ignored and alarm=1; when ack=1 in any cycle the state returns to NORMAL with bad_count=0. alarm=1 only in states 2 and 3. After reset the state is NORMAL and bad_count=0. Sampling clock is 32768 Hz.
S3: Min/max logger (medium)
Design a temperature min/max logger. Inputs: clk; rst_n (active-low asynchronous reset); sample_valid (1-bit strobe); temp (signed 8-bit two's complement, 0.5 degC per LSB); clear (1-bit, synchronous, highest priority). Outputs: t_min (signed 8-bit), t_max (signed 8-bit), valid (1 bit). On reset or when clear=1 at a clock edge: valid=0, t_min=127, t_max=-128. Otherwise, when sample_valid=1: if valid=0 then t_min=t_max=temp and valid=1; else t_min becomes the smaller and t_max the larger of the stored value and temp (signed comparison). Sampling clock is 32768 Hz.
S4: Heat-dose integrator, vial-monitor style (hard)
Design a heat-dose integrator. Parameter THRESH (default 200). Inputs: clk; rst_n (active-low asynchronous reset); sample_valid (1-bit strobe); temp (signed 8-bit two's complement, 0.5 degC per LSB); clear (1-bit, synchronous, highest priority). Outputs: dose (16-bit unsigned), alarm (1 bit). On reset or clear=1 at a clock edge, dose=0. Otherwise when sample_valid=1 and temp > 16 (above 8 degC), dose increases by (temp - 16), saturating at 16'hFFFF (never wrapping). Readings with temp <= 16 leave dose unchanged. alarm=1 whenever dose >= THRESH, else 0. Sampling clock is 32768 Hz.
S5: Ambiguous (must trigger the clarification gate)
Make a chip for the vaccine fridge that warns people when it gets too warm.
What "success" means per spec: S1-S4 end with simulation PASS, a synthesis report and a power estimate. S5 succeeds when the crew stops and asks questions (temperature encoding, threshold, how long before alarming, latched or not). Count that as a pass in your benchmark.

## 7. Member A: LangGraph (stateful graph with a conditional retry loop)
What it shows best: you draw a graph. Nodes are Python functions, edges decide the order, and one shared state dictionary flows through. Loops, branches and "pause for a human" are first-class features.
### 7.1 Install (inside .venv-lg)
pip install langgraph langchain-core langchain-groq requests python-dotenv
# Gemini instead:  pip install langchain-google-genai   -> ChatGoogleGenerativeAI(model=...)
# Ollama instead:  pip install langchain-ollama         -> ChatOllama(model="qwen2.5-coder")
### 7.2 The graph you are building
START -> analyze --(needs clarification)--> END
            |
            v
        write_rtl -> run_lint --(errors & retries<3)--> debug --+
                        | ok                                    |
            (no testbench yet) -> write_tb -> run_sim --FAIL--> debug (retries<3)
                        |                         | PASS         |
                        |                         v              |
                        |                     run_synth          |
                        |                         v              |
                        |                     run_power          |
                        |                         v              |
                        |              [PAUSE: human approval]   |
                        v                         v              |
                     finish <---- (retries exhausted) -----------+
   debug sends an RTL fix back to run_lint and a TB fix straight to run_sim
### 7.3 langgraph_app/run.py (complete)
import os, re, sys, json, time
from typing import TypedDict, List
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from common.prompts import SPEC_SYSTEM, RTL_SYSTEM, TB_SYSTEM, DEBUG_SYSTEM, REPORT_SYSTEM
from common.utils import extract_code, extract_json
from common import tools_client as T

MAX_RETRIES = 3
llm = ChatGroq(model=os.getenv("LLM_MODEL"), temperature=0.2)

def ask(system, user):
    time.sleep(2)                      # free-tier friendliness
    return llm.invoke([SystemMessage(content=system), HumanMessage(content=user)]).content

class S(TypedDict, total=False):       # the shared state
    request: str; spec: dict; rtl: str; tb: str
    lint: dict; sim: dict; synth: dict; pwr: dict
    last_log: str; fail_stage: str; fixed: str
    retries: int; history: List[str]; t0: float; report: str

# ---------- nodes (each returns ONLY the keys it changes) ----------
def analyze(s):
    spec = extract_json(ask(SPEC_SYSTEM, s["request"]))
    return {"spec": spec, "retries": 0, "history": [], "rtl": "", "tb": "", "t0": time.time()}

def write_rtl(s):
    return {"rtl": extract_code(ask(RTL_SYSTEM, "SPEC:\n" + json.dumps(s["spec"], indent=1)))}

def run_lint(s):
    r = T.lint(s["rtl"])
    return {"lint": r, "last_log": r["log"], "fail_stage": "lint"}

def write_tb(s):
    return {"tb": extract_code(ask(TB_SYSTEM, "SPEC:\n" + json.dumps(s["spec"], indent=1)))}

def run_sim(s):
    r = T.simulate(s["rtl"], s["tb"])
    return {"sim": r, "last_log": r["log"], "fail_stage": "sim"}

def debug(s):
    user = (f"SPEC:\n{json.dumps(s['spec'], indent=1)}\n\nRTL:\n{s['rtl']}\n\n"
            f"TESTBENCH:\n{s['tb'] or '(not written yet)'}\n\nLOG ({s['fail_stage']}):\n{s['last_log']}")
    out = ask(DEBUG_SYSTEM, user)
    culprit = "TB" if re.search(r"CULPRIT:\s*TB", out, re.I) else "RTL"
    if s["fail_stage"] == "lint":
        culprit = "RTL"                # a lint failure can only be the RTL
    n = s["retries"] + 1
    return {"tb" if culprit == "TB" else "rtl": extract_code(out),
            "retries": n, "fixed": culprit,
            "history": s["history"] + [f"retry {n} ({s['fail_stage']}): fixed {culprit}"]}

def run_synth(s):
    return {"synth": T.synthesize(s["rtl"], s["spec"]["module_name"])}

def run_power(s):
    sp = s["spec"]
    return {"pwr": T.power(s["sim"]["run_id"], sp.get("clk_hz", 32768), sp.get("power_budget_nw"))}

def finish(s):
    sim = s.get("sim") or {}
    ok = bool(sim.get("passed"))
    synth = {k: v for k, v in (s.get("synth") or {}).items() if k not in ("log", "ctx")}
    bundle = {"status": "PASS" if ok else "FAILED after retries", "spec": s["spec"],
              "sim": {k: sim.get(k) for k in ("passed", "total", "failed", "log")},
              "synth": synth, "power": s.get("pwr"), "history": s["history"],
              "retries": s["retries"], "seconds": round(time.time() - s["t0"], 1)}
    md = ask(REPORT_SYSTEM, json.dumps(bundle, indent=1))
    out = os.path.join("outputs", s["spec"]["module_name"]); os.makedirs(out, exist_ok=True)
    open(f"{out}/design.v", "w").write(s["rtl"])
    open(f"{out}/tb.v", "w").write(s["tb"])
    open(f"{out}/report.md", "w").write(md)
    json.dump({"ok": ok, "retries": s["retries"], "seconds": bundle["seconds"],
               "cells": synth.get("cells"), "power_nw": (s.get("pwr") or {}).get("dynamic_nw")},
              open(f"{out}/metrics.json", "w"))
    return {"report": md}

# ---------- routing (the conditional edges) ----------
def after_analyze(s): return "stop" if s["spec"].get("needs_clarification") else "write_rtl"
def after_lint(s):
    if s["lint"]["ok"]: return "run_sim" if s["tb"] else "write_tb"
    return "debug" if s["retries"] < MAX_RETRIES else "finish"
def after_sim(s):
    if s["sim"]["passed"]: return "run_synth"
    return "debug" if s["retries"] < MAX_RETRIES else "finish"
def after_debug(s): return "run_sim" if s["fixed"] == "TB" else "run_lint"

# ---------- wiring ----------
g = StateGraph(S)
for name, fn in [("analyze", analyze), ("write_rtl", write_rtl), ("run_lint", run_lint),
                 ("write_tb", write_tb), ("run_sim", run_sim), ("debug", debug),
                 ("run_synth", run_synth), ("run_power", run_power), ("finish", finish)]:
    g.add_node(name, fn)
g.add_edge(START, "analyze")
g.add_conditional_edges("analyze", after_analyze, {"stop": END, "write_rtl": "write_rtl"})
g.add_edge("write_rtl", "run_lint")
g.add_conditional_edges("run_lint", after_lint, {"run_sim": "run_sim", "write_tb": "write_tb",
                                                 "debug": "debug", "finish": "finish"})
g.add_edge("write_tb", "run_sim")
g.add_conditional_edges("run_sim", after_sim, {"run_synth": "run_synth", "debug": "debug", "finish": "finish"})
g.add_conditional_edges("debug", after_debug, {"run_sim": "run_sim", "run_lint": "run_lint"})
g.add_edge("run_synth", "run_power")
g.add_edge("run_power", "finish")
g.add_edge("finish", END)

# the graph pauses BEFORE 'finish' so a human can approve (human-in-the-loop)
graph = g.compile(checkpointer=MemorySaver(), interrupt_before=["finish"])

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[2] == "--diagram":
        print(graph.get_graph().draw_mermaid()); sys.exit(0)   # paste into mermaid.live
    request = open(sys.argv[1]).read()
    cfg = {"configurable": {"thread_id": f"run-{int(time.time())}"}}
    graph.invoke({"request": request}, cfg)
    st = graph.get_state(cfg)
    if not st.next:                                   # ended early => clarification gate fired
        print("CLARIFICATION NEEDED:")
        for q in st.values["spec"]["questions"]: print(" -", q)
        sys.exit(0)
    v = st.values
    print("sim passed:", (v.get("sim") or {}).get("passed"), "| retries:", v["retries"], "|", v["history"])
    print("synth:", {k: (v.get("synth") or {}).get(k) for k in ("cells", "dffs", "area_ge")})
    print("power:", v.get("pwr"))
    if input("Approve and write report? [y/N] ").strip().lower() == "y":
        graph.invoke(None, cfg)                       # resume from the checkpoint
        print(graph.get_state(cfg).values["report"])
### 7.4 Run it
python langgraph_app/run.py specs/s2.txt           # headline demo
python langgraph_app/run.py specs/s5.txt           # should print clarification questions
python langgraph_app/run.py specs/s2.txt --diagram # Mermaid text for your poster diagram
Generated files land in outputs/<module_name>/: design.v, tb.v, report.md, metrics.json.
### 7.5 Concepts to explain at the exhibition
| Concept | Where it is in the code | One-line explanation |
| State | class S | One dictionary every node reads and updates |
| Conditional edge | after_lint, after_sim, after_debug | The graph chooses the next node from the state |
| Retry loop | debug edges back to run_lint/run_sim | Real tool errors drive the loop, capped at 3 |
| Checkpointer + interrupt | MemorySaver, interrupt_before | Pauses the run for human approval, then resumes exactly where it stopped |
### 7.6 Definition of done (Member A)
☐ S1-S4 each produce design.v, tb.v, report.md; S5 prints questions.
☐ One recorded run where retries >= 1 (the self-healing moment). If every run passes first time, try S4, which has the most traps.
☐ Mermaid diagram exported for the poster.
☐ Benchmark CSV rows filled (Section 11).

## 8. Member B: n8n (visual workflow, the required block diagram)
What it shows best: the whole pipeline as a drag-and-drop canvas. This is your poster's main block diagram. You build the same logic as LangGraph with boxes and arrows.
### 8.1 Setup
docker compose up -d, then open http://localhost:5678 and create the owner account.
Credentials: add a Groq API credential (or Google Gemini (PaLM) API).
All EDA calls use http://eda:8000 (Docker service name), not localhost.
While building, pin data on the LLM nodes (the pin icon on the output panel) so you do not burn free-tier quota re-running them.
### 8.2 How data travels (read this once, it saves hours)
We keep the entire run in one object called st: { spec, rtl, tb, retries, last_log, fail_stage, fixed, sim, synth, history, t0 }.
HTTP nodes: we send st as ctx and the tool server echoes it back, so the next node reads $json.ctx.
AI Agent nodes: they output only text, so the Code node right after each agent re-reads st from an earlier node with $('Node Name').last().json.
If a value looks stale after a loop, click the node, check its output for the latest run (the run selector at the top of the output panel), and ask Claude with the screenshot (Section 13).
### 8.3 The nodes, lane by lane
Build left to right. Exact node names matter because the Code nodes refer to them.
#### Lane 1: DESIGN
| # | Node name | Type | Settings |
| 1 | Spec Form | Form Trigger | Title "FrostByte"; one field: label Hardware requirement, type Textarea, required |
| 2 | Spec Analyzer | AI Agent | Prompt (Define below): {{ $json['Hardware requirement'] }}. Options, System Message: paste SPEC_SYSTEM. Attach a Groq Chat Model sub-node (temperature 0.2). No tools |
| 3 | Parse Spec | Code (JavaScript) | see below |
| 4 | Needs Clarification? | IF | {{ $json.st.spec.needs_clarification }} is true. True goes to Send Questions (Gmail or Telegram: send message with {{ $json.st.spec.questions.join('\n') }}). False continues |
| 5 | RTL Generator | AI Agent | Prompt: SPEC:\n{{ JSON.stringify($json.st.spec, null, 1) }}; System Message: RTL_SYSTEM; its own Groq Chat Model sub-node |
| 6 | Store RTL | Code | see below |
Parse Spec:
const txt = $input.first().json.output;
const spec = JSON.parse(txt.slice(txt.indexOf('{'), txt.lastIndexOf('}') + 1));
return [{ json: { st: { spec, retries: 0, rtl: '', tb: '', history: [], t0: Date.now() } } }];
Store RTL:
const st = $('Parse Spec').last().json.st;
const out = $input.first().json.output;
const m = out.match(/```(?:verilog|systemverilog|sv|v)?\s*\n([\s\S]*?)```/i);
st.rtl = (m ? m[1] : out).trim() + '\n';
return [{ json: { st } }];
#### Lane 2: VERIFY (the self-healing loop)
| # | Node name | Type | Settings |
| 7 | Lint | HTTP Request | POST http://eda:8000/lint; Send Body on; JSON; body (expression): {{ { design_code: $json.st.rtl, ctx: $json.st } }} |
| 8 | Lint OK? | IF | {{ $json.ok }} is true. True goes to TB Exists?. False goes to Record Lint Failure |
| 9 | Record Lint Failure | Code | see below; connect to Retries Left? |
| 10 | TB Exists? | IF | {{ $json.ctx.tb }} is not empty. True goes to Simulate. False goes to TB Generator |
| 11 | TB Generator | AI Agent | Prompt: SPEC:\n{{ JSON.stringify($json.ctx.spec, null, 1) }}; System Message: TB_SYSTEM; own Groq sub-node |
| 12 | Store TB | Code | see below; connect to Simulate |
| 13 | Simulate | HTTP Request | POST http://eda:8000/simulate; body: {{ { design_code: $json.ctx.rtl, tb_code: $json.ctx.tb, ctx: $json.ctx } }} |
| 14 | Sim PASS? | IF | {{ $json.passed }} is true. True goes to Synthesize. False goes to Record Sim Failure |
| 15 | Record Sim Failure | Code | see below; connect to Retries Left? |
| 16 | Retries Left? | IF | {{ $json.st.retries < 3 }} is true. True goes to Debugger. False goes to Build Failure Report |
| 17 | Debugger | AI Agent | Prompt (below); System Message: DEBUG_SYSTEM; own Groq sub-node |
| 18 | Apply Fix | Code | see below; connect its output back to Lint (this arrow is the loop) |
Record Lint Failure:
const st = $json.ctx; st.last_log = $json.log; st.fail_stage = 'lint';
return [{ json: { st } }];
Store TB:
const st = $('Lint').last().json.ctx;
const out = $input.first().json.output;
const m = out.match(/```(?:verilog|systemverilog|sv|v)?\s*\n([\s\S]*?)```/i);
st.tb = (m ? m[1] : out).trim() + '\n';
return [{ json: { ctx: st } }];
Record Sim Failure:
const st = $json.ctx; st.last_log = $json.log; st.fail_stage = 'sim';
st.sim = { passed: false, total: $json.total, failed: $json.failed };
return [{ json: { st } }];
Debugger prompt (expression):
SPEC:
{{ JSON.stringify($json.st.spec, null, 1) }}

RTL:
{{ $json.st.rtl }}

TESTBENCH:
{{ $json.st.tb || '(not written yet)' }}

LOG ({{ $json.st.fail_stage }}):
{{ $json.st.last_log }}
Apply Fix:
const st = $('Retries Left?').last().json.st;
const out = $input.first().json.output;
const culprit = (/CULPRIT:\s*TB/i.test(out) && st.fail_stage !== 'lint') ? 'TB' : 'RTL';
const m = out.match(/```(?:verilog|systemverilog|sv|v)?\s*\n([\s\S]*?)```/i);
const code = (m ? m[1] : out).trim() + '\n';
if (culprit === 'TB') st.tb = code; else st.rtl = code;
st.retries += 1; st.fixed = culprit;
st.history.push(`retry ${st.retries} (${st.fail_stage}): fixed ${culprit}`);
return [{ json: { st } }];
#### Lane 3: SYNTHESIZE
| # | Node name | Type | Settings |
| 19 | Synthesize | HTTP Request | POST http://eda:8000/synthesize; body: {{ { design_code: $json.ctx.rtl, top: $json.ctx.spec.module_name, ctx: Object.assign({}, $json.ctx, { sim: { passed: $json.passed, total: $json.total, failed: $json.failed, run_id: $json.run_id } }) } }} |
| 20 | Power | HTTP Request | POST http://eda:8000/power; body: {{ { run_id: $json.ctx.sim.run_id, clk_hz: $json.ctx.spec.clk_hz, budget_nw: $json.ctx.spec.power_budget_nw, ctx: Object.assign({}, $json.ctx, { synth: { cells: $json.cells, dffs: $json.dffs, area_ge: $json.area_ge } }) } }} |
#### Lane 4: REPORT
| # | Node name | Type | Settings |
| 21 | Human Approval | Telegram or Gmail, operation Send message and wait for response (approval type) | Message: Sim PASS: {{ $json.ctx.sim.total }} checks. Cells: {{ $json.ctx.synth.cells }}. Power: {{ $json.dynamic_nw }} nW. Approve the report? Only the approved branch continues |
| 22 | Build Report | Code | see below |
| 23 | Build Failure Report | Code | fed by the False branch of Retries Left? |
| 24 | Deliver | Gmail or Telegram | Message: {{ $json.report }} (both report nodes connect here) |
| 25 | Log Metrics | Google Sheets, Append Row | Columns: status, retries, seconds, cells, power_nw. This is your benchmark data source |
Build Report:
const p = $('Power').last().json;
const st = p.ctx;
const secs = Math.round((Date.now() - st.t0) / 1000);
const md = `# ${st.spec.module_name}: FrostByte report
**Status:** PASS (${st.sim.total} checks) | **Retries:** ${st.retries} | **Time:** ${secs}s
## Retry history
${st.history.join('\n') || 'none'}
## Synthesis (Yosys, generic gates)
cells: ${st.synth.cells} | flip-flops: ${st.synth.dffs} | area: ${st.synth.area_ge} GE
## Power (switching-activity estimate)
${p.dynamic_nw} nW vs budget ${p.budget_nw} nW: ${p.within_budget ? 'within budget' : 'OVER budget'}
## RTL
\`\`\`verilog
${st.rtl}\`\`\``;
return [{ json: { report: md, status: 'PASS', retries: st.retries, seconds: secs,
                  cells: st.synth.cells, power_nw: p.dynamic_nw } }];
Build Failure Report:
const st = $json.st;
return [{ json: { report: `FAILED after ${st.retries} retries\nLast log:\n${st.last_log}`,
                  status: 'FAILED', retries: st.retries, seconds: Math.round((Date.now() - st.t0) / 1000) } }];
### 8.4 Sticky notes and the poster screenshot
Add four sticky notes (shortcut: Shift+S) behind the node groups and colour them: 1 DESIGN (nodes 1-6), 2 VERIFY: self-healing loop, max 3 retries (nodes 7-18), 3 SYNTHESIZE (19-20), 4 REPORT (21-25). Press 1 (zoom to fit) and take the screenshot. Also screenshot the Executions tab of a green run where the loop ran, with the Apply Fix arrow visible. Download the workflow JSON (menu, Download) and commit it to GitHub.
For the poster, also draw a clean 4-lane block diagram in draw.io (boxes for nodes, arrows for edges) next to the raw canvas screenshot.
### 8.5 Testing order (do not build everything and then test)
Spec Form to Parse Spec only. Check the JSON parses.
Add RTL Generator, Store RTL, Lint. Paste a deliberately broken RTL to check the failure path.
Add the loop (Debugger, Apply Fix). Confirm retries increments and the loop stops at 3.
Add TB Generator and Simulate.
Add Synthesize, Power, approval, report, Sheets.
The Execute Command node is not needed. Using HTTP to the FastAPI service keeps the workflow working on n8n Cloud as well as self-hosted. If you want an importable workflow JSON afterwards, ask Claude (Section 13) once your hand-built version works, because building it by hand first is how you learn it.
### 8.6 Definition of done (Member B)
☐ Canvas screenshot with 4 labelled lanes; Executions screenshot showing a retry.
☐ S1-S4 run end to end; S5 emails or messages clarification questions.
☐ Human approval step works.
☐ Google Sheet filled with benchmark rows.

## 9. Member C: CrewAI (role-based collaboration)
What it shows best: you define people (agents with a role, goal and backstory) and give them tasks and tools. The agent itself decides when to call a tool. In your design the RTL Designer calls the linter tool on its own until the code compiles, which is the opposite philosophy to LangGraph, where your code owns the loop.
### 9.1 Install and configure (inside .venv-crew)
python3 -m venv .venv-crew && source .venv-crew/bin/activate
pip install crewai requests python-dotenv
Add to .env: CREW_LLM=groq/llama-3.3-70b-versatile (CrewAI uses provider/model names: gemini/<model>, ollama/<model>). If CrewAI complains about an OPENAI_API_KEY, some agent is missing llm=llm.
### 9.2 The crew
| Agent (role) | Job | Tools |
| Spec Analyst | Policy text to JSON spec, or ask for clarification | none |
| RTL Designer | Write Verilog, lint it, fix it | Verilog linter (agent-driven loop) |
| Verification Engineer | Write the testbench from the spec only | none |
| Debug Engineer | Decide RTL vs TB culprit, fix the right file | none |
| Reviewer | Write the final report from real measurements | none |
Design note for your poster: the stages run as separate small crews. We need to stop at the clarification gate, and we need the testbench writer to never see the RTL. Run both in one Crew and CrewAI passes earlier task outputs forward as context, which would leak the RTL into the testbench writer.
### 9.3 crewai_app/run.py (complete)
import os, re, sys, json, time
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
from common.prompts import SPEC_SYSTEM, RTL_SYSTEM, TB_SYSTEM, DEBUG_SYSTEM, REPORT_SYSTEM
from common.utils import extract_code, extract_json
from common import tools_client as T

MAX_RETRIES = 3
llm = LLM(model=os.getenv("CREW_LLM", "groq/llama-3.3-70b-versatile"), temperature=0.2)

@tool("Verilog linter")
def lint_tool(rtl_code: str) -> str:
    """Compile Verilog with iverilog. Returns 'LINT OK' or the compiler errors that must be fixed."""
    r = T.lint(rtl_code)
    return "LINT OK" if r["ok"] else "LINT ERRORS:\n" + r["log"]

def make_agent(role, goal, backstory, tools=None):
    return Agent(role=role, goal=goal, backstory=backstory, tools=tools or [],
                 llm=llm, allow_delegation=False, max_iter=6, verbose=True)

analyst = make_agent("Spec Analyst",
    "Turn a vaccine-storage rule into an unambiguous hardware spec, or ask for clarification",
    "A requirements engineer who has seen projects fail from vague specs. You never invent missing numbers.")
designer = make_agent("RTL Designer",
    "Write synthesizable Verilog that matches the spec and passes the linter",
    "A careful digital designer for ultra-low-power chips. You always run the linter before answering.",
    tools=[lint_tool])
verifier = make_agent("Verification Engineer",
    "Write a self-checking testbench derived only from the spec",
    "A sceptical verification engineer. You have not seen the RTL and you test the rules, not an implementation.")
debugger = make_agent("Debug Engineer",
    "Find whether the RTL or the testbench is wrong and fix only that file",
    "A debugging specialist who always judges against the spec and never weakens a check to get a pass.")
reviewer = make_agent("Reviewer",
    "Write an honest engineering report using only measured numbers",
    "A technical writer who refuses to invent results.")

def run_one(agent, description, expected):
    task = Task(description=description, expected_output=expected, agent=agent)
    Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True).kickoff()
    return task.output.raw

def main(path):
    t0, request = time.time(), open(path).read()
    # NOTE: never pass inputs= to kickoff; our prompts contain { } (JSON) which CrewAI would try to interpolate.

    # Stage 1: spec + clarification gate
    spec = extract_json(run_one(analyst, SPEC_SYSTEM + "\n\nUSER REQUEST:\n" + request,
                                "A single JSON object and nothing else."))
    if spec.get("needs_clarification"):
        print("\nCLARIFICATION NEEDED:"); [print(" -", q) for q in spec["questions"]]; return
    spec_txt = json.dumps(spec, indent=1)

    # Stage 2: RTL (the agent loops on the lint tool by itself) and TB (separate crew, never sees RTL)
    rtl = extract_code(run_one(designer,
        RTL_SYSTEM + "\n\nSPEC:\n" + spec_txt +
        "\n\nBefore answering, call the Verilog linter tool on your code. Fix any reported errors "
        "(at most 3 attempts), then output only the final ```verilog block.",
        "One ```verilog block that passes the linter."))
    tb = extract_code(run_one(verifier, TB_SYSTEM + "\n\nSPEC:\n" + spec_txt, "One ```verilog block."))

    # Stage 3: verify, with a supervised debug loop
    retries, history = 0, []
    while True:
        lint = T.lint(rtl)
        sim = T.simulate(rtl, tb) if lint["ok"] else {"passed": False, "log": lint["log"]}
        stage = "sim" if lint["ok"] else "lint"
        if sim["passed"] or retries >= MAX_RETRIES: break
        retries += 1
        out = run_one(debugger,
            DEBUG_SYSTEM + f"\n\nSPEC:\n{spec_txt}\n\nRTL:\n{rtl}\n\nTESTBENCH:\n{tb}\n\nLOG ({stage}):\n{sim['log']}",
            "First line CULPRIT: RTL or CULPRIT: TB, then one ```verilog block.")
        culprit = "TB" if (re.search(r"CULPRIT:\s*TB", out, re.I) and stage == "sim") else "RTL"
        if culprit == "TB": tb = extract_code(out)
        else: rtl = extract_code(out)
        history.append(f"retry {retries} ({stage}): fixed {culprit}")

    ok = bool(sim["passed"])
    synth, pwr = {}, {}
    if ok:
        synth = T.synthesize(rtl, spec["module_name"])
        pwr = T.power(sim["run_id"], spec.get("clk_hz", 32768), spec.get("power_budget_nw"))
    print("\nsim passed:", ok, "| retries:", retries, history)
    print("synth:", {k: synth.get(k) for k in ("cells", "dffs", "area_ge")}, "| power:", pwr.get("dynamic_nw"))

    # Stage 4: human approval, then the Reviewer writes the report
    if input("Approve and write report? [y/N] ").strip().lower() != "y": return
    bundle = {"status": "PASS" if ok else "FAILED after retries", "spec": spec,
              "sim": {k: sim.get(k) for k in ("passed", "total", "failed", "log")},
              "synth": {k: v for k, v in synth.items() if k not in ("log", "ctx")},
              "power": pwr, "history": history, "retries": retries,
              "seconds": round(time.time() - t0, 1)}
    md = run_one(reviewer, REPORT_SYSTEM + "\n\nBUNDLE:\n" + json.dumps(bundle, indent=1), "A markdown report.")
    out = os.path.join("outputs", spec["module_name"]); os.makedirs(out, exist_ok=True)
    open(f"{out}/design.v", "w").write(rtl); open(f"{out}/tb.v", "w").write(tb)
    open(f"{out}/report.md", "w").write(md)
    json.dump({"ok": ok, "retries": retries, "seconds": bundle["seconds"], "cells": synth.get("cells"),
               "power_nw": pwr.get("dynamic_nw")}, open(f"{out}/metrics.json", "w"))
    print(md)

if __name__ == "__main__":
    main(sys.argv[1])
Run: python crewai_app/run.py specs/s2.txt. The verbose log (each agent's "thought", tool call and result) is great poster material: screenshot the part where the Designer calls the linter, reads an error and fixes it.
### 9.4 Definition of done (Member C)
☐ S1-S4 pass end to end; S5 asks questions.
☐ Screenshot of the Designer calling the linter tool autonomously.
☐ A one-slide explanation of "agent-driven loop (CrewAI) vs graph-driven loop (LangGraph)".
☐ Benchmark rows filled.

## 10. Member D: Dify (visual LLM app builder)
What it shows best: a product-like app: a web UI and an API generated for you, with built-in model management and run logs. It is a second visual platform, so what you show is how a managed builder differs from n8n. If Docker memory is a problem, swap in Flowise and keep the same stages.
### 10.1 Setup
git clone https://github.com/langgenius/dify.git && cd dify/docker
cp .env.example .env && docker compose up -d
# open http://localhost/install and create the admin account
Then Settings, Model Provider: add Groq (or Gemini) with your API key.
### 10.2 Import the EDA tools
Open http://localhost:8000/openapi.json and copy the JSON.
In Dify: Tools, Custom, Create Custom Tool, paste it into the Schema box.
FastAPI does not state its server address. Add "servers": [{"url": "http://host.docker.internal:8000"}] at the top level of the JSON (on Linux use your machine's LAN IP).
Click Test on /lint. You now have four tools: lint, simulate, synthesize, power.
### 10.3 Build a Workflow app (not Chatflow)
Dify workflows are a one-way graph (no arrows back), so the retry loop is unrolled: Attempt 1, then Debug and Attempt 2, then Debug and Attempt 3. Use a Loop node instead only if your Dify version offers it and you are comfortable with it. The unrolling is an honest finding for the comparison table.
| Order | Node | Type | Notes |
| 1 | Start | Start | Input variable request (paragraph) |
| 2 | Spec Analyzer | LLM | System prompt: SPEC_SYSTEM; user: the request variable |
| 3 | Parse Spec | Code (Python) | see below; outputs spec (string), ask (number 0/1), questions (string), module (string) |
| 4 | Needs Clarification? | IF/ELSE | ask equals 1 goes to an End node returning questions |
| 5 | RTL Generator | LLM | RTL_SYSTEM; user: SPEC: plus the spec variable |
| 6 | Extract RTL | Code | see below |
| 7 | Lint | Tool (custom) | design_code is rtl |
| 8 | Lint OK? | IF/ELSE | If false: Debugger LLM, Extract RTL again, Lint again (attempt 2, then 3) |
| 9 | TB Generator + Extract TB | LLM + Code | TB_SYSTEM, spec only |
| 10 | Simulate | Tool | design_code, tb_code |
| 11 | Sim PASS? | IF/ELSE | If false: Debugger, then Simulate again (unrolled, max 2 more) |
| 12 | Synthesize, Power | Tools | top is module; Power takes run_id from Simulate |
| 13 | End | End | Outputs: rtl, tb, simulation log, synth numbers, power |
Code node snippets (Dify uses a main function; declare the output names and types in the node panel):
import json
def main(text: str) -> dict:
    spec = json.loads(text[text.find("{"): text.rfind("}") + 1])
    return {"spec": json.dumps(spec), "ask": 1 if spec.get("needs_clarification") else 0,
            "questions": "\n".join(spec.get("questions", [])), "module": spec.get("module_name", "top")}

import re
def main(text: str) -> dict:
    m = re.search(r"```(?:verilog|systemverilog|sv|v)?\s*\n(.*?)```", text, re.S | re.I)
    return {"rtl": (m.group(1) if m else text).strip() + "\n"}
Publish the app: Publish, Run App gives a shareable web page. Put its QR code on the poster. Dify's per-node Run Log panel is your "Output samples" evidence.
### 10.4 Definition of done (Member D)
☐ Workflow canvas screenshot; one run log screenshot per stage.
☐ S1-S4 run; S5 returns questions.
☐ A short note on how the retry loop had to be unrolled and what Dify gives you instead (UI, API, logs).
☐ Benchmark rows filled.

## 11. Benchmark and comparison
### 11.1 Protocol (every member, same rules)
10 runs per platform: S1 x2, S2 x3, S3 x2, S4 x2, S5 x1. LLMs are random, which is why repeats matter.
Same LLM and temperature on every platform if at all possible. Write the model name on the poster.
Success = for S1-S4: simulation PASS and synthesis ran. For S5: the system asked clarification questions and did not write RTL.
Log one CSV row per run in benchmark/results.csv:
platform,spec,run,success,retries,seconds,cells,power_nw,failure_reason
langgraph,S2,1,1,1,74,,,
(metrics.json from LangGraph and CrewAI has the numbers; n8n gets them from the Google Sheet; Dify from the run log.)
### 11.2 Summary script (benchmark/summary.py)
import csv, collections
rows = list(csv.DictReader(open("benchmark/results.csv")))
by = collections.defaultdict(list)
for r in rows: by[r["platform"]].append(r)
for p, rs in by.items():
    n = len(rs); ok = sum(int(r["success"]) for r in rs)
    print(f"{p:10s} success {ok}/{n}  avg retries {sum(float(r['retries'] or 0) for r in rs)/n:.2f}"
          f"  avg time {sum(float(r['seconds'] or 0) for r in rs)/n:.0f}s")
### 11.3 The ablation that wins marks
Run S2 and S4 five times each with MAX_RETRIES = 0 and again with 3 (LangGraph is the easiest place to flip this). Report both success rates. If the self-healing loop raises the success rate, you have measured evidence that real tool feedback helps. If it does not, report that honestly. Both are good results.
### 11.4 Comparison table (fill in after your runs; do not copy guesses)
| Dimension | LangGraph | n8n | CrewAI | Dify |
| Success rate (of 10) |  |  |  |  |
| Avg retries |  |  |  |  |
| Avg seconds per run |  |  |  |  |
| Retry loop | explicit conditional edges | arrow back to Lint | agent calls tool itself + Python loop | unrolled (DAG) |
| Human-in-the-loop | interrupt + checkpoint | approval node | input() | (your finding) |
| Time to first working version |  |  |  |  |
| Debugging experience |  |  |  |  |
| Best for |  |  |  |  |

## 12. Poster kit
### 12.1 Panels (A1/A2 landscape)
Title + team: "FrostByte: Agents that turn vaccine cold-chain rules into verified silicon"; platform logo; SDG 3 icon.
Problem and objective (text below).
Block diagram: your platform's diagram (n8n: the canvas plus the clean 4-lane diagram; LangGraph: Mermaid export; CrewAI: draw.io of agents and tools; Dify: workflow canvas).
Input samples (left): S2 text; S5 ambiguous text.
Output samples (right): design.v excerpt, testbench log line (TEST_RESULT: PASS total=N failed=0), Yosys cell table, power line, retry history, S5 clarification questions.
Key features.
Results table (your benchmark) and the platform comparison.
SDG mapping (SDG 3 primary, 9 and 4 supporting) and limitations.
QR codes: GitHub repo, demo video.
### 12.2 Ready-to-edit text blocks
Problem: Vaccines must stay within a narrow temperature range from factory to clinic. Both heat and accidental freezing can damage them, and the damage is invisible to the naked eye. Monitoring devices need tiny, always-on, battery-powered logic, but designing and verifying custom chips is slow and needs specialist skills.
Objective: Build an agentic system that converts a plain-English storage rule into synthesizable Verilog, verifies it with a real simulator, self-corrects from real tool errors, and reports area and a power estimate, using only open-source EDA tools.
Key features:
Policy-to-silicon: plain English in, verified Verilog out
Clarification gate: ambiguous requests get questions, not guesses
Testbench written from the spec only, never from the RTL
Self-healing loop driven by compiler and simulator output (max 3 retries)
Debugger decides whether the RTL or the testbench is at fault
Synthesis report (cells, flip-flops, gate-equivalent area) and a switching-activity power estimate against a budget
100% open-source toolchain (Icarus Verilog, Yosys)
Same use case on four agent platforms, measured
Limitations (put these on the poster, it builds trust): generic-gate synthesis, not a real cell library; power is a switching-activity estimate with accelerated stimulus; simulation only, no silicon; LLM output varies between runs; the policy values in our specs are illustrative and must be checked against official WHO/UNICEF documents before any real use.
### 12.3 Three-minute demo script
(20 s) Run S5 ("warn when too warm"). The crew asks questions. "It refuses to guess."
(60 s) Run S2. Narrate each stage as it runs. Show a retry if one happens.
(40 s) Show the testbench result line, the Yosys numbers and the power line.
(30 s) Show the human-approval step and the final report.
(30 s) Point at the comparison table: "Same task, four platforms, here is what we measured."
Record a clean run as a backup video in case Wi-Fi or the free API tier fails at the exhibition. Free tiers rate-limit at the worst moment.
### 12.4 Questions judges will ask (rehearse these)
| Question | Strong answer |
| Why not just ask ChatGPT for the Verilog? | A chatbot cannot prove its answer. Ours compiles, simulates against spec-derived tests, synthesizes, and fixes itself from real tool errors. |
| What if the testbench is wrong? | It is written from the spec only, and the debugger can blame the testbench, but only judged against the spec. We never allow weakening a check. |
| Is the power number real? | No. It is a switching-activity estimate with stated assumptions, good for comparing designs. Silicon power needs a real cell library and layout. |
| How is this about SDGs? | We started from SDG 3 (vaccine access) and asked what chip logic protects vaccines, then built the tool for that. |
| What did the benchmark show? | Quote your own numbers, including failures and the 0-retry versus 3-retry ablation. |
| What would you do next? | Real cell library (Sky130) for area, a formal-property check, a policy library per vaccine type. |

## 13. Prompt cookbook: using Claude as your coding partner
Golden rules: paste the exact error text (not a paraphrase); say which platform and version (pip show langgraph); ask for the smallest change that fixes it; ask Claude to explain what it changed so you can answer judges' questions.
Understand a piece of code
I'm new to LangGraph. Explain this file section by section like I'm a second-year engineering student.
Tell me what each function receives and returns, and where the retry loop is. [paste code]
Fix an error
Platform: CrewAI <version>, Python 3.11, Ubuntu/WSL2.
I ran: python crewai_app/run.py specs/s2.txt
Full error: [paste the whole traceback]
Here is the relevant code: [paste]. Give me the smallest fix and explain the cause in 2 sentences.
n8n stuck
In n8n, my Code node 'Apply Fix' reads $('Retries Left?').last().json.st but st.retries is still 0 on the
second loop. Here is the node output screenshot/JSON: [paste]. What is going wrong and how do I make the state reliable?
Generate the importable n8n workflow (only after you have built it by hand once)
Here are my node names, types and settings from the handbook table [paste]. Generate an importable n8n workflow
JSON with the same nodes and connections. List anything I must fill in manually (credentials, URLs).
Add rate-limit handling
My ask() function in common calls Groq and gets HTTP 429 on the free tier. Write a retry-with-exponential-backoff
wrapper (max 5 tries, jitter) and show where to use it.
Add a new spec
Here is spec S2 and the shared prompts. Write a new spec 'S6' (a 10-minute sample-tick prescaler from a 32768 Hz clock,
parameterised so the testbench can use a small count) in the same style, with exact boundaries and no ambiguity.
Poster and viva
Here are my real benchmark results [paste table]. Write the 'Results' panel text (max 80 words), then ask me five
tough viva questions about my project one at a time and critique my answers.
Do not ask Claude to invent benchmark numbers, citations or SDG statistics. Ask it to help you find where to look, then verify yourself.

## 14. Troubleshooting
| Symptom | Cause | Fix |
| iverilog is not installed from the tool server | Running native without the package | sudo apt install iverilog yosys, or use Docker |
| n8n cannot reach the tools (ECONNREFUSED localhost:8000) | localhost inside Docker is the n8n container | Use http://eda:8000 |
| Dify cannot reach the tools | Same, different network | Use http://host.docker.internal:8000 or the LAN IP |
| synthesize returns cells: 0 | Yosys stat layout differs from the regex | Print log from the response, adapt the two regexes in /synthesize (ask Claude with the log) |
| /power says wave.vcd not found | Testbench missing $dumpfile("wave.vcd") | It is mandatory in TB_SYSTEM; check the generated TB |
| Power is 0 or tiny | Instance not named dut, so no signals counted | TB_SYSTEM requires dut; check the TB |
| Simulation hangs | TB has no $finish or an endless loop | The 30 s timeout returns a TIMEOUT log; the debugger sees it |
| TEST_RESULT missing, passed: false | TB printed a different result line | Debugger fixes it; check the prompt text is exactly as given |
| LLM returns text around the JSON or code | Normal LLM behaviour | extract_json and extract_code handle it; do not remove them |
| HTTP 429 or quota errors | Free-tier rate limit | Longer time.sleep, backoff wrapper (Section 13), pin data in n8n, switch to Ollama |
| LangGraph: node name equals a state key | Reserved clash (for example a node called report while report is a state key) | Rename the node (we use finish) |
| CrewAI wants OPENAI_API_KEY | An agent has no llm= | Pass llm=llm to every agent |
| CrewAI mangles prompts with braces | inputs= interpolation | Never pass inputs=; build strings in Python |
| Same bug every retry | Debugger sees too little | Make sure the log, spec, RTL and TB are all in the debug prompt |
| S4 keeps failing | Genuinely hardest spec (width and saturation traps) | Report it honestly, and show the failure reason and the 3-retry history; this is a result |

## 15. Timeline, ownership and final checklist
| Day | Team | Output |
| 1 | Everyone | Read Sections 1-3. Re-score the SDG scorecard together. Set up repo, Docker, .env. |
| 2 | Everyone (pair up) | Tool server running; smoke.py passes; shared prompts and 5 specs committed. |
| 3 | Each member | Own-platform skeleton: spec stage plus clarification gate working. |
| 4 | Each member | RTL, lint, retry loop working on S1. |
| 5 | Each member | Testbench, simulation, debug loop on S1-S2. |
| 6 | Each member | Synthesis, power, approval, report; S3-S4. |
| 7 | Everyone | Benchmark (11.1), ablation (11.3), comparison table, record backup demo videos. |
| 8 | Everyone | Posters, QR codes, README, rehearse demo and viva. |
Final checklist
☐ Repo on GitHub with README: one-command start (docker compose up), how to run each platform, sample outputs
☐ .env is not committed; .env.example is
☐ Each platform runs S1-S4 and handles S5
☐ Real numbers only on posters; limitations panel included
☐ SDG panel states the SDG-first reasoning (Section 1 scorecard as a small table)
☐ Backup demo video recorded, and a local fallback (Ollama or pre-saved outputs) ready
☐ Every member can explain, without notes: the state or data flow, the retry loop, why the testbench never sees the RTL, and what the power number is and is not
"""HTTP client for the shared EDA tool server (handbook 6.2).

EDA_URL is read at import time; load .env before importing this module."""
import os, requests
BASE = os.getenv("EDA_URL", "http://localhost:8000")

def _post(path, payload):
    r = requests.post(BASE + path, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()

def lint(rtl):               return _post("/lint", {"design_code": rtl})
def simulate(rtl, tb):       return _post("/simulate", {"design_code": rtl, "tb_code": tb})
def synthesize(rtl, top):    return _post("/synthesize", {"design_code": rtl, "top": top})
def power(run_id, clk_hz=32768, budget_nw=None, tb_clk_ns=10.0):
    # Fix vs handbook: tb_clk_ns is passed through so the cycle count matches the testbench clock.
    return _post("/power", {"run_id": run_id, "clk_hz": clk_hz, "budget_nw": budget_nw,
                            "tb_clk_ns": tb_clk_ns})

def health():
    r = requests.get(BASE + "/health", timeout=5); r.raise_for_status(); return r.json()

"""Tool-server tests (needs the server running: docker compose up -d eda).

Agentic AI concept: these guard the TOOLS, the agent's only source of ground truth.
"""
import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import tools_client as T  # noqa: E402

CNT = """module cnt(input clk, input rst_n, output reg [3:0] q);
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

# A testbench that "passes" without checking anything: must NOT count as a pass.
VACUOUS_TB = """`timescale 1ns/1ps
module tb; reg clk=0, rst_n=0; wire [3:0] q;
cnt dut(.clk(clk), .rst_n(rst_n), .q(q));
initial begin $display("TEST_RESULT: PASS total=0 failed=0"); $finish; end
endmodule"""


@pytest.fixture(scope="module", autouse=True)
def server_up():
    try:
        T.health()
    except requests.RequestException:
        pytest.skip("EDA tool server not running (docker compose up -d eda)")


def test_health():
    assert T.health() == {"ok": True}


def test_lint_ok_and_ctx_echo():
    r = requests.post(T.BASE + "/lint", json={"design_code": CNT, "ctx": {"k": [1, 2]}}).json()
    assert r["ok"] is True
    assert r["ctx"] == {"k": [1, 2]}          # ctx is echoed back unchanged


def test_lint_error():
    r = T.lint(CNT.replace("q <= 0;", "q <= 0"))   # missing semicolon
    assert r["ok"] is False and "error" in r["log"].lower()


def test_simulate_pass():
    s = T.simulate(CNT, TB)
    assert s["passed"] is True and s["total"] == 1 and s["failed"] == 0


def test_vacuous_pass_blocked():
    s = T.simulate(CNT, VACUOUS_TB)
    assert "TEST_RESULT: PASS" in s["log"]
    assert s["passed"] is False               # total=0 -> not a pass


def test_synth_and_power():
    y = T.synthesize(CNT, "cnt")
    assert y["ok"] and y["dffs"] == 4 and y["cells"] > 0 and y["area_ge"] > 0
    s = T.simulate(CNT, TB)
    p = T.power(s["run_id"], budget_nw=100, tb_clk_ns=10)
    assert p["ok"] is True and p["dynamic_nw"] > 0 and p["within_budget"] is True

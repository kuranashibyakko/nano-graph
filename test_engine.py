import pytest
from engine import StateGraph, END
from checkpoint import MemoryCheckpointer

def test_linear_graph():
    graph = StateGraph()
    graph.add_node("step1", lambda s: {"x": s["x"] + 1})
    graph.add_node("step2", lambda s: {"x": s["x"] * 10})
    graph.set_entry_point("step1")
    graph.add_edge("step1", "step2")

    res = graph.invoke({"x": 2})
    assert res["x"] == 30
    assert res["_trace"] == ["step1", "step2"]


def test_cyclic_conditional_graph():
    graph = StateGraph()
    graph.add_node("inc", lambda s: {"count": s["count"] + 1})
    graph.set_entry_point("inc")
    graph.add_conditional_edge("inc", lambda s: END if s["count"] >= 3 else "inc")

    res = graph.invoke({"count": 0})
    assert res["count"] == 3
    assert res["_trace"] == ["inc", "inc", "inc"]


def test_max_steps_protection():
    graph = StateGraph()
    graph.add_node("loop", lambda s: {"count": s["count"] + 1})
    graph.set_entry_point("loop")
    graph.add_edge("loop", "loop")

    with pytest.raises(RuntimeError, match="Max graph steps exceeded"):
        graph.invoke({"count": 0}, max_steps=4)



def test_checkpoint_and_time_travel():
    cp = MemoryCheckpointer()
    graph = StateGraph(checkpointer=cp)

    graph.add_node("step1", lambda s: {"val": s["val"] + 10})
    graph.add_node("step2", lambda s: {"val": s["val"] * 2})
    graph.add_node("step3", lambda s: {"val": s["val"] - 5})

    graph.set_entry_point("step1")
    graph.add_edge("step1", "step2")
    graph.add_edge("step2", "step3")

    # 1. Full run: (5 + 10) * 2 - 5 = 25
    final = graph.invoke({"val": 5}, thread_id="run_1")
    assert final["val"] == 25

    # 2. Inspect checkpoint at step 1 (right after step1 finished: val == 15)
    snap_1 = cp.get_checkpoint_at_step("run_1", step=1)
    assert snap_1 is not None
    assert snap_1["node"] == "step1"
    assert snap_1["state"]["val"] == 15

    # 3. Time-travel: Modify state at step 1 (change val from 15 to 100) and resume at step2!
    rewound_state = snap_1["state"]
    rewound_state["val"] = 100
    resumed_final = graph.invoke(rewound_state, thread_id="run_1_fork", start_at="step2")

    # (100 * 2) - 5 = 195
    assert resumed_final["val"] == 195
    assert resumed_final["_trace"] == ["step1", "step2", "step3"]
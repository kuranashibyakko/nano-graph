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


def test_human_in_the_loop_interrupt_and_resume():
    graph = StateGraph()
    graph.add_node("draft_sql", lambda s: {"query": "DELETE FROM users"})
    graph.add_node("execute_sql", lambda s: {"executed": s["query"]})

    graph.set_entry_point("draft_sql")
    graph.add_edge("draft_sql", "execute_sql")

    # 1. Run with breakpoint before 'execute_sql'
    paused = graph.invoke({"query": "", "executed": None}, interrupt_before=["execute_sql"])
    assert paused["_interrupted_at"] == "execute_sql"
    assert paused["query"] == "DELETE FROM users"
    assert paused["executed"] is None  # Prove execute_sql did NOT run yet!
    assert paused["_trace"] == ["draft_sql"]

    # 2. Human edits the dangerous query in state and resumes at 'execute_sql'
    paused["query"] = "SELECT * FROM users"
    final = graph.invoke(paused, start_at="execute_sql", interrupt_before=["execute_sql"])

    assert "_interrupted_at" not in final
    assert final["executed"] == "SELECT * FROM users"
    assert final["_trace"] == ["draft_sql", "execute_sql"]


def test_to_mermaid_generation():
    def my_router(state: dict) -> str:
        return END

    graph = StateGraph()
    graph.add_node("gen", lambda s: s)
    graph.add_node("exec", lambda s: s)
    graph.set_entry_point("gen")
    graph.add_edge("gen", "exec")
    graph.add_conditional_edge("exec", my_router)

    diagram = graph.to_mermaid()
    assert "graph TD" in diagram
    assert "START((START)) --> gen" in diagram
    assert "gen --> exec" in diagram
    assert "exec -.->|my_router| exec_router{Router}" in diagram
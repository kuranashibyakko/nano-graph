import pytest
from engine import StateGraph, END


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

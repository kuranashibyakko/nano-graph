import copy
from typing import Callable, Any

END = "END"


class StateGraph:
    """A lightweight, cyclic state-machine engine for AI agents."""

    def __init__(self, checkpointer=None):
        self.nodes: dict[str, Callable[[dict], dict]] = {}
        self.edges: dict[str, str] = {}
        self.conditional_edges: dict[str, Callable[[dict], str]] = {}
        self.entry_point: str | None = None
        self.checkpointer = checkpointer

    def add_node(self, name: str, func: Callable[[dict], dict]) -> None:
        """Registers a node function in the graph."""

        self.nodes[name] = func

    def set_entry_point(self, name: str) -> None:
        """Sets the starting node name for graph execution."""

        self.entry_point = name

    def add_edge(self, from_node: str, to_node: str) -> None:
        """Adds a fixed directed edge from `from_node` to `to_node`."""

        self.edges[from_node] = to_node

    def add_conditional_edge(self, from_node: str, router_fn: Callable[[dict], str]) -> None:
        """Adds a dynamic conditional edge where `router_fn(state)` returns the next node name."""

        self.conditional_edges[from_node] = router_fn

    def invoke(self, initial_state: dict[str, Any], max_steps: int = 10,thread_id: str = "default",start_at: str | None = None,) -> dict[str, Any]:
        """Executes the state graph starting from `entry_point` until `END` is reached."""
        if not self.entry_point:
            raise ValueError("Graph entry_point is not set.")

        # Make a deep copy so we don't mutate the caller's original dict
        state = copy.deepcopy(initial_state)
        state.setdefault("_trace", [])  # Tracks the sequence of visited node names

        current_node = start_at or self.entry_point
        steps = 0

        while current_node != END:
            if steps >= max_steps:
                raise RuntimeError("Max graph steps exceeded")

            if current_node not in self.nodes:
                raise KeyError(f"Unknown node: {current_node}")
            
            state["_trace"].append(current_node)
            steps+=1

            updates = self.nodes[current_node](state)

            if isinstance(updates, dict):
                state.update(updates)
            
            if self.checkpointer is not None:
                self.checkpointer.save_checkpoint(thread_id, steps, current_node, state)

            if current_node in self.conditional_edges:
                current_node = self.conditional_edges[current_node](state)
            
            elif current_node in self.edges:
                current_node = self.edges[current_node]
            else:
                current_node = END
            
        return state



if __name__ == "__main__":

    def double_node(state: dict) -> dict:
        new_val = state["value"] * 2
        print(f"  [double_node] {state['value']} -> {new_val}")
        return {"value": new_val, "loops": state["loops"] + 1}

    def audit_router(state: dict) -> str:
        if state["value"] >= 20:
            return END
        return "doubler"

    graph = StateGraph()
    graph.add_node("doubler", double_node)
    graph.set_entry_point("doubler")
    graph.add_conditional_edge("doubler", audit_router)

    print("🚀 Running nano-graph self-test...")
    final_state = graph.invoke({"value": 3, "loops": 0})
    print("\n✅ Final State:", final_state)

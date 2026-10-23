import copy
from typing import Any


class MemoryCheckpointer:
    """Stores step-by-step state snapshots per thread_id for inspection and time-travel."""

    def __init__(self):
        # Maps thread_id -> list of checkpoint dicts
        self.storage: dict[str, list[dict[str, Any]]] = {}

    def save_checkpoint(self, thread_id: str, step: int, node_name: str, state: dict[str, Any]) -> None:
        """Saves a deep-copied snapshot of the state after a node finishes."""

        if thread_id not in self.storage:
            self.storage[thread_id] = []

        self.storage[thread_id].append({
                "step": step,
                "node": node_name,
                "state": copy.deepcopy(state)
            })
        



    def get_history(self, thread_id: str) -> list[dict[str, Any]]:
        """Returns the list of all saved checkpoints for a thread_id."""

        return self.storage.get(thread_id, [])

    def get_checkpoint_at_step(self, thread_id: str, step: int) -> dict[str, Any] | None:
        """Finds and returns a deep copy of the checkpoint dict at a specific step number."""

        for item in self.get_history(thread_id):
            if item["step"] == step:
                return copy.deepcopy(item)
        return None 


        
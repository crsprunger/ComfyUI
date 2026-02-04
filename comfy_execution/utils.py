import contextvars
from typing import NamedTuple, FrozenSet

class ExecutionContext(NamedTuple):
    """
    Context information about the currently executing node.

    Attributes:
        prompt_id: The ID of the current prompt execution
        node_id: The ID of the currently executing node
        list_index: The index in a list being processed (for operations on batches/lists)
        expected_outputs: Set of output indices that might be used downstream.
                         Outputs NOT in this set are definitely unused (safe to skip).
                         None means the information is not available.
    """
    prompt_id: str
    node_id: str
    list_index: int | None
    expected_outputs: FrozenSet[int] | None = None

current_executing_context: contextvars.ContextVar[ExecutionContext | None] = contextvars.ContextVar("current_executing_context", default=None)

def get_executing_context() -> ExecutionContext | None:
    return current_executing_context.get(None)

class CurrentNodeContext:
    """
    Context manager for setting the current executing node context.

    Sets the current_executing_context on enter and resets it on exit.

    Example:
        with CurrentNodeContext(prompt_id="abc", node_id="123", list_index=0):
            # Code that should run with the current node context set
            process_image()
    """
    def __init__(
        self,
        prompt_id: str,
        node_id: str,
        list_index: int | None = None,
        expected_outputs: FrozenSet[int] | None = None,
    ):
        self.context = ExecutionContext(
            prompt_id=prompt_id,
            node_id=node_id,
            list_index=list_index,
            expected_outputs=expected_outputs,
        )
        self.token = None

    def __enter__(self):
        self.token = current_executing_context.set(self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token is not None:
            current_executing_context.reset(self.token)

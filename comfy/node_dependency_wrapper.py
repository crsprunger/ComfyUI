"""
Dynamic node wrapper for adding dependency inputs/outputs from UI.

This module provides two approaches for adding dependency inputs/outputs to
existing nodes without modifying their source code:

1. NODE_CLASS_MAPPINGS wrapper - Apply decorator to specific nodes at load time
2. Universal wrapper nodes - Wrap any node dynamically from the UI

Usage for approach 1 (in custom node __init__.py):
    from comfy.node_dependency_wrapper import wrap_node_classes

    # Define which nodes to wrap and how
    NODES_TO_WRAP = {
        "CLIPTextEncode": {"add_output": True},
        "SaveImage": {"input_name": "wait_for"},
        "LoadImage": {},  # Use defaults
    }

    # Wrap the nodes
    NODE_CLASS_MAPPINGS = wrap_node_classes(NODE_CLASS_MAPPINGS, NODES_TO_WRAP)

Usage for approach 2 (use in workflow UI):
    Add "Add Dependency Input" or "Add Dependency IO" nodes to your workflow
    and connect them before/after the target nodes.
"""

import copy
from typing import Dict, Any, Tuple
from comfy.node_dependency import add_dependency_input
from comfy.comfy_types.node_typing import IO


def wrap_node_classes(
    node_mappings: Dict[str, type],
    nodes_to_wrap: Dict[str, Dict[str, Any]]
) -> Dict[str, type]:
    """
    Apply dependency decorator to specified nodes in NODE_CLASS_MAPPINGS.

    This function is designed to be used in custom node __init__.py files
    to automatically add dependency inputs/outputs to existing nodes.

    Args:
        node_mappings: The NODE_CLASS_MAPPINGS dictionary
        nodes_to_wrap: Dict mapping node names to decorator parameters
                      Format: {"NodeName": {"input_name": "...", "add_output": True, ...}}

    Returns:
        Modified NODE_CLASS_MAPPINGS with wrapped nodes

    Example:
        NODE_CLASS_MAPPINGS = {
            "MyNode": MyNodeClass,
            "OtherNode": OtherNodeClass,
        }

        NODES_TO_WRAP = {
            "MyNode": {"add_output": True, "input_name": "depends_on"},
            "OtherNode": {"required": True},
        }

        NODE_CLASS_MAPPINGS = wrap_node_classes(NODE_CLASS_MAPPINGS, NODES_TO_WRAP)
    """
    wrapped_mappings = copy.copy(node_mappings)

    for node_name, decorator_params in nodes_to_wrap.items():
        if node_name in wrapped_mappings:
            # Get the original class
            original_class = wrapped_mappings[node_name]

            # Apply the decorator with specified parameters
            wrapped_class = add_dependency_input(**decorator_params)(original_class)

            # Replace in mappings
            wrapped_mappings[node_name] = wrapped_class

            print(f"[node_dependency_wrapper] Wrapped '{node_name}' with params: {decorator_params}")

    return wrapped_mappings


def apply_decorator_to_node(node_class: type, **decorator_params) -> type:
    """
    Apply dependency decorator to a single node class.

    Args:
        node_class: The node class to wrap
        **decorator_params: Parameters to pass to add_dependency_input

    Returns:
        Wrapped node class
    """
    return add_dependency_input(**decorator_params)(node_class)


# ============================================================================
# Universal Wrapper Nodes for UI-based wrapping
# ============================================================================

class AddDependencyInput:
    """
    UI node that adds a dependency input to any node's execution.

    This node passes through all data unchanged but creates an execution
    dependency. Use it to force a specific execution order.

    Workflow usage:
        [NodeA] → value → [AddDependencyInput] → value → [NodeB]
        [NodeC] → signal → [AddDependencyInput.depends_on]

    Result: NodeC executes before NodeA, even though NodeB uses NodeA's value.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": (IO.ANY, {}),
            },
            "optional": {
                "depends_on": (IO.ANY, {}),
            }
        }

    RETURN_TYPES = (IO.ANY,)
    RETURN_NAMES = ("value",)
    FUNCTION = "passthrough"
    CATEGORY = "utils/dependencies"

    def passthrough(self, value, depends_on=None):
        """Pass through the value unchanged, creating dependency."""
        return (value,)


class AddDependencyIO:
    """
    UI node that adds both dependency input and passthrough output.

    This node passes through data and the dependency signal, enabling
    chaining of dependencies.

    Workflow usage:
        [NodeA] → signal → [AddDependencyIO.depends_on]
        [NodeA] → value → [AddDependencyIO.value]
        [AddDependencyIO.value] → [NodeB]
        [AddDependencyIO.signal_out] → [NodeC.depends_on]

    Result: Creates dependency chain with signal propagation.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": (IO.ANY, {}),
            },
            "optional": {
                "depends_on": (IO.ANY, {}),
            }
        }

    RETURN_TYPES = (IO.ANY, IO.ANY)
    RETURN_NAMES = ("value", "signal_out")
    FUNCTION = "passthrough_with_signal"
    CATEGORY = "utils/dependencies"

    def passthrough_with_signal(self, value, depends_on=None):
        """Pass through both value and dependency signal."""
        return (value, depends_on)


class DependencyBarrier:
    """
    UI node that acts as a synchronization barrier.

    All dependency inputs must be satisfied before the value passes through.
    Useful for ensuring multiple nodes complete before proceeding.

    Workflow usage:
        [NodeA] → [DependencyBarrier.dep1]
        [NodeB] → [DependencyBarrier.dep2]
        [NodeC] → [DependencyBarrier.dep3]
        [SomeValue] → [DependencyBarrier.value] → [NextNode]

    Result: NextNode only executes after NodeA, NodeB, and NodeC all complete.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": (IO.ANY, {}),
            },
            "optional": {
                "dep1": (IO.ANY, {}),
                "dep2": (IO.ANY, {}),
                "dep3": (IO.ANY, {}),
                "dep4": (IO.ANY, {}),
                "dep5": (IO.ANY, {}),
            }
        }

    RETURN_TYPES = (IO.ANY,)
    RETURN_NAMES = ("value",)
    FUNCTION = "barrier"
    CATEGORY = "utils/dependencies"

    def barrier(self, value, dep1=None, dep2=None, dep3=None, dep4=None, dep5=None):
        """Pass through value after all dependencies are satisfied."""
        return (value,)


class DependencySignal:
    """
    UI node that generates a signal for dependency tracking.

    Creates a signal value that can be passed through dependency chains
    without affecting actual data flow.

    Workflow usage:
        [DependencySignal] → signal → [Node.depends_on]

    The signal can be:
    - Empty (None) - just for ordering
    - Integer counter - for tracking execution order
    - String message - for debugging/logging
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "signal_type": (["empty", "counter", "message"], {"default": "empty"}),
            },
            "optional": {
                "counter_value": ("INT", {"default": 0, "min": 0, "max": 999999}),
                "message": ("STRING", {"default": "signal", "multiline": False}),
            }
        }

    RETURN_TYPES = (IO.ANY,)
    RETURN_NAMES = ("signal",)
    FUNCTION = "generate_signal"
    CATEGORY = "utils/dependencies"

    def generate_signal(self, signal_type, counter_value=0, message="signal"):
        """Generate a dependency signal based on type."""
        if signal_type == "empty":
            return (None,)
        elif signal_type == "counter":
            return (counter_value,)
        elif signal_type == "message":
            return (message,)
        return (None,)


# ============================================================================
# ComfyUI Node Registration
# ============================================================================

NODE_CLASS_MAPPINGS = {
    "AddDependencyInput": AddDependencyInput,
    "AddDependencyIO": AddDependencyIO,
    "DependencyBarrier": DependencyBarrier,
    "DependencySignal": DependencySignal,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AddDependencyInput": "Add Dependency Input",
    "AddDependencyIO": "Add Dependency I/O",
    "DependencyBarrier": "Dependency Barrier",
    "DependencySignal": "Dependency Signal",
}

__all__ = [
    'wrap_node_classes',
    'apply_decorator_to_node',
    'AddDependencyInput',
    'AddDependencyIO',
    'DependencyBarrier',
    'DependencySignal',
    'NODE_CLASS_MAPPINGS',
    'NODE_DISPLAY_NAME_MAPPINGS',
]

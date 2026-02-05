"""
Universal dependency input decorator for ComfyUI nodes.

This module provides a decorator that adds a "dummy" dependency input to any
ComfyUI node. When connected, this input forces the upstream node to execute
first, enabling explicit control over execution order without affecting the
node's internal behavior.

Basic Usage:
    from comfy.node_dependency import add_dependency_input

    @add_dependency_input()
    class MyNode:
        @classmethod
        def INPUT_TYPES(s):
            return {"required": {"value": ("FLOAT", {})}}

        RETURN_TYPES = ("FLOAT",)
        FUNCTION = "process"

        def process(self, value):
            return (value * 2,)

    # In workflow: NodeA.output → NodeB.depends_on
    # Result: NodeA executes before NodeB

Chaining Dependencies with Passthrough Output:
    @add_dependency_input(add_output=True)
    class ChainableNode:
        # Node definition...

    # In workflow: NodeA → NodeB.depends_on → NodeC.depends_on
    # The dependency value passes through NodeB to NodeC
    # Result: NodeA → NodeB → NodeC (guaranteed execution order)

The decorator adds an optional input (default name: "depends_on") of type IO.ANY
that accepts any connection. With add_output=True, it also adds a passthrough
output that returns the dependency input value, enabling dependency chaining.
"""

import inspect
import functools
from typing import Callable, Any
from comfy.comfy_types.node_typing import IO


def _add_output_type(node_class, output_name: str = None):
    """
    Add IO.ANY to RETURN_TYPES and optionally update RETURN_NAMES.

    Args:
        node_class: The node class to modify
        output_name: Optional name for the output (for RETURN_NAMES)
    """
    # Modify RETURN_TYPES
    if hasattr(node_class, 'RETURN_TYPES'):
        original_types = node_class.RETURN_TYPES
        if isinstance(original_types, tuple):
            node_class.RETURN_TYPES = original_types + (IO.ANY,)
        elif isinstance(original_types, list):
            node_class.RETURN_TYPES = tuple(original_types) + (IO.ANY,)

    # Modify RETURN_NAMES if it exists and output_name is provided
    if output_name and hasattr(node_class, 'RETURN_NAMES'):
        original_names = node_class.RETURN_NAMES
        if isinstance(original_names, tuple):
            node_class.RETURN_NAMES = original_names + (output_name,)
        elif isinstance(original_names, list):
            node_class.RETURN_NAMES = tuple(original_names) + (output_name,)
    elif output_name and hasattr(node_class, 'RETURN_TYPES'):
        # Create RETURN_NAMES if it doesn't exist but output_name is provided
        num_outputs = len(node_class.RETURN_TYPES)
        # Last one is the dependency output we just added
        node_class.RETURN_NAMES = tuple([f"output_{i}" for i in range(num_outputs - 1)] + [output_name])


def _wrap_input_types(original_method: classmethod, input_name: str, required: bool) -> Callable:
    """
    Modify INPUT_TYPES classmethod to add dependency input.

    Args:
        original_method: Original INPUT_TYPES classmethod
        input_name: Name of the dependency input
        required: Whether input should be required or optional

    Returns:
        New INPUT_TYPES function that includes the dependency input
    """
    @functools.wraps(original_method.__func__)
    def new_input_types(cls):
        # Call original INPUT_TYPES to get base inputs
        inputs = original_method.__func__(cls)

        # Add dependency input to appropriate category
        category = "required" if required else "optional"
        inputs.setdefault(category, {})

        # Use IO.ANY to accept any type of connection
        inputs[category][input_name] = (IO.ANY, {})

        return inputs

    return new_input_types


def _wrap_execution_method(original_func: Callable, param_name: str, add_output: bool = False) -> Callable:
    """
    Wrap execution method to accept dummy parameter without affecting behavior.

    This function extends the execution method's signature to include the
    dependency input parameter with a default value of None. The wrapper
    removes this parameter before calling the original function.

    Args:
        original_func: Original execution method
        param_name: Name of the dependency parameter
        add_output: If True, append the dependency value to the return tuple

    Returns:
        Wrapped function with extended signature
    """
    try:
        # Get original function signature
        sig = inspect.signature(original_func)

        # Create new parameter with default None
        new_param = inspect.Parameter(
            param_name,
            inspect.Parameter.KEYWORD_ONLY,
            default=None
        )

        # Add new parameter to signature
        new_params = list(sig.parameters.values()) + [new_param]

        @functools.wraps(original_func)
        def wrapper(*args, **kwargs):
            # Extract dependency value before removing it
            dep_value = kwargs.pop(param_name, None)

            # Call original function
            result = original_func(*args, **kwargs)

            # If add_output is True, append dependency value to result
            if add_output:
                # Ensure result is a tuple
                if not isinstance(result, tuple):
                    result = (result,)
                # Append the dependency value
                result = result + (dep_value,)

            return result

        # Attach new signature for introspection
        wrapper.__signature__ = sig.replace(parameters=new_params)
        return wrapper

    except (ValueError, TypeError) as e:
        # If signature inspection fails (e.g., built-in functions, *args/**kwargs),
        # fall back to simple wrapper that just pops the parameter
        @functools.wraps(original_func)
        def simple_wrapper(*args, **kwargs):
            dep_value = kwargs.pop(param_name, None)
            result = original_func(*args, **kwargs)

            if add_output:
                if not isinstance(result, tuple):
                    result = (result,)
                result = result + (dep_value,)

            return result

        return simple_wrapper


def add_dependency_input(
    input_name: str = "depends_on",
    required: bool = False,
    add_output: bool = False,
    output_name: str = None
):
    """
    Decorator that adds a dummy dependency input to any ComfyUI node.

    This decorator modifies a node class to include an additional input that
    accepts any type (IO.ANY). When another node's output is connected to this
    input, it creates a dependency in ComfyUI's execution graph, forcing the
    upstream node to execute first.

    Args:
        input_name: Name of the dependency input (default: "depends_on")
        required: If True, input is required; if False, optional (default: False)
                 Note: Using required=True will break existing workflows that
                 don't have this connection, so optional is recommended.
        add_output: If True, also add a passthrough output that returns the
                   dependency input value (default: False). This enables chaining
                   dependencies across multiple nodes.
        output_name: Name for the passthrough output in RETURN_NAMES. If not
                    specified, uses input_name + "_out" (only used if add_output=True)

    Returns:
        Class decorator function

    Example:
        @add_dependency_input()
        class MyNode:
            @classmethod
            def INPUT_TYPES(s):
                return {
                    "required": {
                        "value": ("FLOAT", {"default": 1.0})
                    }
                }

            RETURN_TYPES = ("FLOAT",)
            FUNCTION = "process"

            def process(self, value):
                return (value * 2,)

        # In workflow: NodeA.output → NodeB.depends_on
        # Result: NodeA executes before NodeB

    Example with passthrough output for chaining:
        @add_dependency_input(add_output=True)
        class ChainableNode:
            # Node definition...
            pass

        # In workflow: NodeA → NodeB.depends_on → NodeC.depends_on
        # Result: NodeA → NodeB → NodeC (guaranteed order)

    Example with custom names:
        @add_dependency_input(input_name="wait_for", output_name="waited")
        class OrderedNode:
            # Node definition...
            pass
    """
    def decorator(node_class):
        """
        Actual decorator that modifies the node class.

        Args:
            node_class: The ComfyUI node class to modify

        Returns:
            Modified node class with dependency input and optional output
        """
        # Step 1: Wrap INPUT_TYPES to add dependency input
        if hasattr(node_class, 'INPUT_TYPES'):
            original_input_types = node_class.INPUT_TYPES
            wrapped_input_types = _wrap_input_types(original_input_types, input_name, required)
            node_class.INPUT_TYPES = classmethod(wrapped_input_types)

        # Step 2: Add passthrough output if requested
        if add_output:
            # Determine output name
            out_name = output_name if output_name else f"{input_name}_out"
            _add_output_type(node_class, out_name)

        # Step 3: Wrap execution method to accept dependency parameter
        # Try to find the function name from FUNCTION attribute, fallback to 'execute'
        func_name = getattr(node_class, 'FUNCTION', 'execute')

        if hasattr(node_class, func_name):
            original_func = getattr(node_class, func_name)

            # Handle both instance methods and classmethods
            if isinstance(original_func, classmethod):
                # For classmethods, wrap the underlying function
                wrapped_func = _wrap_execution_method(original_func.__func__, input_name, add_output)
                setattr(node_class, func_name, classmethod(wrapped_func))
            else:
                # For regular methods, wrap directly
                wrapped_func = _wrap_execution_method(original_func, input_name, add_output)
                setattr(node_class, func_name, wrapped_func)

        return node_class

    return decorator


# For convenience, provide a shorthand version with sensible defaults
def depends_on(node_class):
    """
    Shorthand decorator that adds a "depends_on" optional input.

    This is equivalent to @add_dependency_input() with default parameters.

    Example:
        @depends_on
        class MyNode:
            # Node definition...
            pass
    """
    return add_dependency_input()(node_class)

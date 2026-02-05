# Universal Node Dependency Decorator - Usage Guide

## Overview

The `add_dependency_input` decorator allows you to add a "dummy" dependency input to any ComfyUI node. This enables explicit control over execution order without modifying the node's internal behavior.

## Quick Start

```python
from comfy.node_dependency import add_dependency_input

@add_dependency_input()
class MyCustomNode:
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
```

## How It Works

1. **Adds an Optional Input**: The decorator adds an optional input (default name: `"depends_on"`) of type `IO.ANY` to your node
2. **Creates Dependencies**: When you connect another node's output to this input, ComfyUI's execution system ensures the upstream node executes first
3. **Ignores the Value**: The input value is automatically removed before calling your node's execution method, so it doesn't affect your code

## Use Cases

### Scenario 1: Force Execution Order

You have two nodes that don't naturally depend on each other, but you need one to run before the other:

```
[NodeA] ──output──> (normal use)
   │
   └──any_output──> [NodeB.depends_on]

Result: NodeA executes before NodeB
```

### Scenario 2: Ensure Side Effects Happen First

NodeA has side effects (saves a file, updates a database, etc.) that must complete before NodeB runs:

```python
@add_dependency_input()
class NodeB:
    # Your node definition
    pass
```

Connect NodeA's output to NodeB's `depends_on` input.

### Scenario 3: Complex Execution Chains

Create explicit dependency chains across multiple nodes:

```
[A] ──> [B.depends_on] ──> [C.depends_on] ──> [D.depends_on]

Guaranteed order: A → B → C → D
```

## Advanced Usage

### Custom Input Name

```python
@add_dependency_input(input_name="wait_for")
class MyNode:
    # Node definition
    pass
```

The input will appear as `wait_for` in the UI instead of `depends_on`.

### Required Dependency (Use with Caution)

```python
@add_dependency_input(required=True)
class StrictOrderNode:
    # Node definition
    pass
```

⚠️ **Warning**: This breaks backward compatibility! Existing workflows using this node will fail unless they connect something to the dependency input.

### Multiple Dependencies

You can apply the decorator multiple times to add multiple dependency inputs:

```python
@add_dependency_input(input_name="dep1")
@add_dependency_input(input_name="dep2")
class MultiDepNode:
    # Node definition
    pass
```

This node will wait for both `dep1` and `dep2` to be satisfied before executing.

### Shorthand Decorator

For quick use with default settings:

```python
from comfy.node_dependency import depends_on

@depends_on
class QuickNode:
    # Node definition
    pass
```

Equivalent to `@add_dependency_input()` with all defaults.

## Compatibility

### Works With

✅ Instance methods (`def execute(self, ...)`)
✅ Class methods (`@classmethod def execute(cls, ...)`)
✅ Nodes with existing optional inputs
✅ Nodes with `**kwargs` signatures
✅ Custom function names (via `FUNCTION` attribute)
✅ `INPUT_IS_LIST` nodes
✅ Multiple decorator applications

### Node Types

The decorator works with all ComfyUI node patterns:
- Classic nodes (instance methods)
- V3 API nodes (classmethods)
- Nodes with custom `FUNCTION` attributes
- Nodes with various input configurations

## Real-World Example

Let's say you have a workflow where:
1. `SaveImageNode` saves an image to disk
2. `ProcessImageNode` needs to read that file

Without dependencies, `ProcessImageNode` might try to read the file before `SaveImageNode` finishes saving it.

**Solution:**

```python
from comfy.node_dependency import add_dependency_input

@add_dependency_input()
class ProcessImageNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "filepath": ("STRING", {})
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "load_and_process"

    def load_and_process(self, filepath):
        # Read and process the file
        # The depends_on parameter is automatically handled
        image = load_image(filepath)
        return (process(image),)
```

**Workflow:**
```
[SaveImageNode] ──saved_file──> [ProcessImageNode.filepath]
              └──output────────> [ProcessImageNode.depends_on]

Now ProcessImageNode is guaranteed to run after SaveImageNode completes!
```

## Technical Details

### How Dependencies Are Created

ComfyUI's execution system uses a topological sort algorithm to determine node execution order. When you connect an output to an input:
1. A link is created: `[source_node_id, output_index]`
2. The execution graph traverses these links backward from each node
3. All upstream nodes must complete before downstream nodes execute

The `depends_on` input participates in this system just like any other input.

### Why the Value Is Ignored

Your node's execution method signature is extended to accept the dependency parameter with a default value of `None`. When your method is called, the decorator wrapper removes this parameter before passing the arguments to your original code.

**Original function:**
```python
def process(self, value):
    return (value * 2,)
```

**After decoration:**
```python
def process(self, value, depends_on=None):  # Signature extended
    # depends_on is removed here
    return original_process(self, value)  # Called without depends_on
```

### Signature Inspection

The decorator properly updates the function signature so tools like `inspect.signature()` will show the dependency parameter. This ensures compatibility with ComfyUI's validation and introspection systems.

## Best Practices

1. **Prefer Optional**: Use `required=False` (default) to maintain backward compatibility
2. **Descriptive Names**: Use `input_name` parameter to give meaningful names to dependencies
3. **Document Intent**: Add comments explaining why the dependency is needed
4. **Test Workflows**: Verify execution order with logging or prints during development
5. **Minimal Use**: Only add dependencies where truly needed; excessive dependencies can make workflows rigid

## Troubleshooting

### Input Doesn't Appear in UI

- Make sure the decorator is applied before the node class is registered with ComfyUI
- Check that the node has `INPUT_TYPES` classmethod
- Restart ComfyUI to reload node definitions

### Execution Order Not Working

- Verify the connection is actually made in the workflow
- Ensure the input is not marked as `lazy=True` (the decorator doesn't do this, but manual modifications might)
- Check ComfyUI's execution logs for topological sort results

### Parameter Signature Errors

- The decorator should handle most cases automatically
- If you get signature-related errors, ensure your execution method has a standard signature
- Methods with only `*args` or complex signature patterns should still work via kwargs.pop()

## Files

- **Implementation**: [comfy/node_dependency.py](comfy/node_dependency.py)
- **Tests**: [test_node_dependency.py](test_node_dependency.py)
- **Run tests**: `./.venv/bin/python3 test_node_dependency.py`

## Further Reading

- ComfyUI Execution System: `comfy_execution/graph.py`
- Input Type System: `comfy/comfy_types/node_typing.py`
- Node Examples: `nodes.py`, `comfy_extras/nodes_*.py`

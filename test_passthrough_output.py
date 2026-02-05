#!/usr/bin/env python3
"""
Test file for passthrough output functionality.

This script tests the add_output parameter of the add_dependency_input decorator
to ensure dependency chaining works correctly.

Run with: ./.venv/bin/python3 test_passthrough_output.py
"""

import sys
import inspect
from comfy.node_dependency import add_dependency_input
from comfy.comfy_types.node_typing import IO


print("=" * 80)
print("Testing ComfyUI Dependency Passthrough Output")
print("=" * 80)


# Test 1: Basic passthrough output
print("\n[Test 1] Basic passthrough output")
print("-" * 80)

@add_dependency_input(add_output=True)
class TestPassthroughNode:
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


# Verify RETURN_TYPES was modified
return_types = TestPassthroughNode.RETURN_TYPES
print(f"RETURN_TYPES: {return_types}")
assert len(return_types) == 2, f"Should have 2 return types, got {len(return_types)}"
assert return_types[0] == "FLOAT", "First return should be FLOAT"
assert return_types[1] == IO.ANY, "Second return should be IO.ANY"
print("✓ RETURN_TYPES correctly modified")

# Test execution with passthrough
node = TestPassthroughNode()
result = node.process(value=5.0, depends_on="test_value")
print(f"Result: {result}")
assert len(result) == 2, f"Should return 2 values, got {len(result)}"
assert result[0] == 10.0, f"First return should be 10.0, got {result[0]}"
assert result[1] == "test_value", f"Second return should be 'test_value', got {result[1]}"
print("✓ Passthrough output works correctly")

# Test with None dependency
result = node.process(value=5.0, depends_on=None)
assert result[1] is None, f"Passthrough should be None, got {result[1]}"
print("✓ Passthrough works with None")

# Test without dependency parameter
result = node.process(value=3.0)
assert len(result) == 2, "Should still return 2 values"
assert result[0] == 6.0, "First return should be 6.0"
assert result[1] is None, "Passthrough should be None when not provided"
print("✓ Passthrough works when dependency not provided")


# Test 2: Custom output name
print("\n[Test 2] Custom output name")
print("-" * 80)

@add_dependency_input(add_output=True, output_name="signal_out")
class TestCustomOutputName:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "text": ("STRING", {"default": "hello"})
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("processed",)
    FUNCTION = "process"

    def process(self, text):
        return (text.upper(),)


return_names = TestCustomOutputName.RETURN_NAMES
print(f"RETURN_NAMES: {return_names}")
assert len(return_names) == 2, "Should have 2 return names"
assert return_names[0] == "processed", "First name should be 'processed'"
assert return_names[1] == "signal_out", "Second name should be 'signal_out'"
print("✓ Custom output name works")


# Test 3: Chaining simulation
print("\n[Test 3] Chaining simulation")
print("-" * 80)

@add_dependency_input(add_output=True)
class ChainNode1:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {"val": ("INT", {"default": 0})}}

    RETURN_TYPES = ("INT",)
    FUNCTION = "run"

    def run(self, val):
        return (val + 1,)


@add_dependency_input(add_output=True)
class ChainNode2:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {"val": ("INT", {"default": 0})}}

    RETURN_TYPES = ("INT",)
    FUNCTION = "run"

    def run(self, val):
        return (val + 10,)


@add_dependency_input(add_output=True)
class ChainNode3:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {"val": ("INT", {"default": 0})}}

    RETURN_TYPES = ("INT",)
    FUNCTION = "run"

    def run(self, val):
        return (val + 100,)


# Simulate chained execution
print("Simulating: Chain1 → Chain2 → Chain3")

node1 = ChainNode1()
node2 = ChainNode2()
node3 = ChainNode3()

# Node1 executes with initial signal
result1 = node1.run(val=1)  # No dependency
print(f"  Node1 result: {result1}")
assert result1 == (2, None), f"Node1 should return (2, None), got {result1}"

# Node2 executes with Node1's passthrough
result2 = node2.run(val=2, depends_on=result1[1])  # Uses Node1's passthrough
print(f"  Node2 result: {result2}")
assert result2 == (12, None), f"Node2 should return (12, None), got {result2}"

# Node3 executes with Node2's passthrough
result3 = node3.run(val=3, depends_on=result2[1])  # Uses Node2's passthrough
print(f"  Node3 result: {result3}")
assert result3 == (103, None), f"Node3 should return (103, None), got {result3}"

print("✓ Chaining works correctly")


# Test 4: Passthrough with actual signal
print("\n[Test 4] Passthrough with signal value")
print("-" * 80)

# Simulate a chain where the signal carries data
result1 = node1.run(val=1, depends_on="start_signal")
print(f"  Node1 result: {result1}")
assert result1[1] == "start_signal", "Node1 should pass through the signal"

result2 = node2.run(val=2, depends_on=result1[1])
print(f"  Node2 result: {result2}")
assert result2[1] == "start_signal", "Node2 should pass through the signal"

result3 = node3.run(val=3, depends_on=result2[1])
print(f"  Node3 result: {result3}")
assert result3[1] == "start_signal", "Node3 should pass through the signal"

print("✓ Signal propagates through chain")


# Test 5: Different data types in passthrough
print("\n[Test 5] Different data types in passthrough")
print("-" * 80)

@add_dependency_input(add_output=True)
class FlexibleNode:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {"x": ("INT", {})}}

    RETURN_TYPES = ("INT",)
    FUNCTION = "compute"

    def compute(self, x):
        return (x ** 2,)


node = FlexibleNode()

# Test with different types
test_values = [
    42,
    "string_value",
    [1, 2, 3],
    {"key": "value"},
    None,
    3.14159,
]

for test_val in test_values:
    result = node.compute(x=5, depends_on=test_val)
    assert result[0] == 25, "First return should always be 25"
    assert result[1] == test_val, f"Passthrough should preserve {type(test_val).__name__}"
    print(f"  ✓ {type(test_val).__name__}: {repr(test_val)} → {repr(result[1])}")

print("✓ Passthrough preserves all data types")


# Test 6: Classmethod with passthrough
print("\n[Test 6] Classmethod with passthrough")
print("-" * 80)

@add_dependency_input(add_output=True)
class ClassmethodPassthrough:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"data": ("STRING", {})}}

    RETURN_TYPES = ("STRING",)
    FUNCTION = "execute"

    @classmethod
    def execute(cls, data):
        return (f"Processed: {data}",)


return_types = ClassmethodPassthrough.RETURN_TYPES
assert len(return_types) == 2, "Should have 2 return types"
assert return_types[1] == IO.ANY, "Second return should be IO.ANY"

result = ClassmethodPassthrough.execute(data="test", depends_on="signal")
assert result == ("Processed: test", "signal"), f"Expected ('Processed: test', 'signal'), got {result}"
print("✓ Classmethod passthrough works")


# Test 7: Multiple returns with passthrough
print("\n[Test 7] Multiple returns with passthrough")
print("-" * 80)

@add_dependency_input(add_output=True)
class MultiReturnNode:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {"x": ("INT", {})}}

    RETURN_TYPES = ("INT", "INT", "INT")
    RETURN_NAMES = ("squared", "cubed", "quadrupled")
    FUNCTION = "compute"

    def compute(self, x):
        return (x**2, x**3, x**4)


return_types = MultiReturnNode.RETURN_TYPES
print(f"RETURN_TYPES: {return_types}")
assert len(return_types) == 4, "Should have 4 return types"
assert return_types[-1] == IO.ANY, "Last return should be IO.ANY"

return_names = MultiReturnNode.RETURN_NAMES
print(f"RETURN_NAMES: {return_names}")
assert len(return_names) == 4, "Should have 4 return names"
assert return_names[-1] == "depends_on_out", "Last name should be depends_on_out"

node = MultiReturnNode()
result = node.compute(x=2, depends_on="my_signal")
print(f"Result: {result}")
assert result == (4, 8, 16, "my_signal"), f"Expected (4, 8, 16, 'my_signal'), got {result}"
print("✓ Multiple returns with passthrough works")


# Summary
print("\n" + "=" * 80)
print("ALL PASSTHROUGH TESTS PASSED! ✓")
print("=" * 80)
print("\nThe passthrough output feature successfully:")
print("  • Adds IO.ANY output to RETURN_TYPES")
print("  • Passes through dependency input value unchanged")
print("  • Enables chaining dependencies across nodes")
print("  • Works with custom output names")
print("  • Preserves all data types")
print("  • Works with both instance and class methods")
print("  • Works with multiple return values")
print("\nDependency chaining is ready to use!")
print("=" * 80)

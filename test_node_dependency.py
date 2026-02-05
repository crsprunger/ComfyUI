#!/usr/bin/env python3
"""
Test file for the node_dependency decorator.

This script tests the add_dependency_input decorator with various node types
to ensure it works correctly across different ComfyUI node patterns.

Run with: ./.venv/bin/python3 test_node_dependency.py
"""

import sys
import inspect
from comfy.node_dependency import add_dependency_input, depends_on
from comfy.comfy_types.node_typing import IO


print("=" * 80)
print("Testing ComfyUI Node Dependency Decorator")
print("=" * 80)


# Test 1: Basic node with instance method
print("\n[Test 1] Basic node with instance method")
print("-" * 80)

@add_dependency_input()
class TestBasicNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "value": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0})
            }
        }

    RETURN_TYPES = ("FLOAT",)
    FUNCTION = "process"
    CATEGORY = "testing"

    def process(self, value):
        """Process the value."""
        return (value * 2,)


# Verify INPUT_TYPES was modified
input_types = TestBasicNode.INPUT_TYPES()
print(f"INPUT_TYPES: {input_types}")

assert "optional" in input_types, "Should have optional inputs"
assert "depends_on" in input_types["optional"], "Should have depends_on input"
assert input_types["optional"]["depends_on"] == (IO.ANY, {}), "depends_on should be IO.ANY type"
print("✓ INPUT_TYPES correctly modified")

# Verify execution method signature
sig = inspect.signature(TestBasicNode.process)
params = list(sig.parameters.keys())
print(f"Execution method parameters: {params}")
assert "depends_on" in params, "Signature should include depends_on parameter"
print("✓ Execution method signature extended")

# Test execution without dependency input
node = TestBasicNode()
result = node.process(value=5.0)
assert result == (10.0,), f"Expected (10.0,), got {result}"
print("✓ Execution works without depends_on parameter")

# Test execution with dependency input (should be ignored)
result = node.process(value=5.0, depends_on="some_value")
assert result == (10.0,), f"Expected (10.0,), got {result}"
print("✓ Execution works with depends_on parameter (ignored)")


# Test 2: Node with custom input name
print("\n[Test 2] Node with custom input name")
print("-" * 80)

@add_dependency_input(input_name="wait_for")
class TestCustomNameNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "text": ("STRING", {"default": "hello"})
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "process"

    def process(self, text):
        return (text.upper(),)


input_types = TestCustomNameNode.INPUT_TYPES()
print(f"INPUT_TYPES: {input_types}")
assert "wait_for" in input_types["optional"], "Should have wait_for input"
print("✓ Custom input name works")

node = TestCustomNameNode()
result = node.process(text="hello", wait_for=None)
assert result == ("HELLO",), f"Expected ('HELLO',), got {result}"
print("✓ Execution with custom parameter name works")


# Test 3: Required dependency input
print("\n[Test 3] Required dependency input")
print("-" * 80)

@add_dependency_input(input_name="must_wait", required=True)
class TestRequiredNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "value": ("INT", {"default": 0})
            }
        }

    RETURN_TYPES = ("INT",)
    FUNCTION = "compute"

    def compute(self, value):
        return (value + 1,)


input_types = TestRequiredNode.INPUT_TYPES()
print(f"INPUT_TYPES: {input_types}")
assert "required" in input_types, "Should have required inputs"
assert "must_wait" in input_types["required"], "must_wait should be in required"
print("✓ Required dependency input works")


# Test 4: Node with classmethod execution (V3 API style)
print("\n[Test 4] Node with classmethod execution")
print("-" * 80)

@add_dependency_input()
class TestClassmethodNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "data": ("STRING", {})
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "execute"

    @classmethod
    def execute(cls, data):
        return (f"Processed: {data}",)


input_types = TestClassmethodNode.INPUT_TYPES()
print(f"INPUT_TYPES: {input_types}")
assert "depends_on" in input_types["optional"], "Should have depends_on input"
print("✓ INPUT_TYPES modified for classmethod node")

result = TestClassmethodNode.execute(data="test")
assert result == ("Processed: test",), f"Expected ('Processed: test',), got {result}"
print("✓ Classmethod execution works without dependency")

result = TestClassmethodNode.execute(data="test", depends_on=42)
assert result == ("Processed: test",), f"Expected ('Processed: test',), got {result}"
print("✓ Classmethod execution works with dependency (ignored)")


# Test 5: Shorthand decorator
print("\n[Test 5] Shorthand @depends_on decorator")
print("-" * 80)

@depends_on
class TestShorthandNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "x": ("FLOAT", {"default": 0.0})
            }
        }

    RETURN_TYPES = ("FLOAT",)
    FUNCTION = "run"

    def run(self, x):
        return (x ** 2,)


input_types = TestShorthandNode.INPUT_TYPES()
print(f"INPUT_TYPES: {input_types}")
assert "depends_on" in input_types["optional"], "Should have depends_on input"
print("✓ Shorthand decorator works")

node = TestShorthandNode()
result = node.run(x=3.0)
assert result == (9.0,), f"Expected (9.0,), got {result}"
print("✓ Shorthand decorator execution works")


# Test 6: Node with existing optional inputs
print("\n[Test 6] Node with existing optional inputs")
print("-" * 80)

@add_dependency_input()
class TestExistingOptionalNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "value": ("INT", {"default": 1})
            },
            "optional": {
                "multiplier": ("FLOAT", {"default": 1.0})
            }
        }

    RETURN_TYPES = ("FLOAT",)
    FUNCTION = "calculate"

    def calculate(self, value, multiplier=1.0):
        return (value * multiplier,)


input_types = TestExistingOptionalNode.INPUT_TYPES()
print(f"INPUT_TYPES: {input_types}")
assert "multiplier" in input_types["optional"], "Should preserve existing optional input"
assert "depends_on" in input_types["optional"], "Should add depends_on input"
print("✓ Preserves existing optional inputs")

node = TestExistingOptionalNode()
result = node.calculate(value=5, multiplier=2.0, depends_on=None)
assert result == (10.0,), f"Expected (10.0,), got {result}"
print("✓ Works with multiple optional parameters")


# Test 7: Multiple decorator applications
print("\n[Test 7] Multiple dependency inputs")
print("-" * 80)

@add_dependency_input(input_name="dep1")
@add_dependency_input(input_name="dep2")
class TestMultipleDepsNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "data": ("STRING", {})
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "process"

    def process(self, data):
        return (data,)


input_types = TestMultipleDepsNode.INPUT_TYPES()
print(f"INPUT_TYPES: {input_types}")
assert "dep1" in input_types["optional"], "Should have dep1 input"
assert "dep2" in input_types["optional"], "Should have dep2 input"
print("✓ Multiple dependency inputs work")

node = TestMultipleDepsNode()
result = node.process(data="test", dep1=None, dep2=None)
assert result == ("test",), f"Expected ('test',), got {result}"
print("✓ Multiple dependencies handled correctly")


# Test 8: Node with **kwargs in signature
print("\n[Test 8] Node with **kwargs in signature")
print("-" * 80)

@add_dependency_input()
class TestKwargsNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "value": ("INT", {"default": 0})
            }
        }

    RETURN_TYPES = ("INT",)
    FUNCTION = "process"

    def process(self, **kwargs):
        """Process with kwargs."""
        value = kwargs.get("value", 0)
        # depends_on should be removed before this is called
        assert "depends_on" not in kwargs, "depends_on should be removed"
        return (value,)


node = TestKwargsNode()
result = node.process(value=42, depends_on="ignored")
assert result == (42,), f"Expected (42,), got {result}"
print("✓ Works with **kwargs signature (depends_on removed)")


# Summary
print("\n" + "=" * 80)
print("ALL TESTS PASSED! ✓")
print("=" * 80)
print("\nThe decorator successfully:")
print("  • Adds dependency inputs to various node types")
print("  • Extends execution method signatures")
print("  • Preserves original node behavior")
print("  • Handles optional and required modes")
print("  • Works with custom input names")
print("  • Supports both instance and class methods")
print("  • Handles multiple applications")
print("  • Works with **kwargs signatures")
print("\nThe decorator is ready to use in ComfyUI workflows!")
print("=" * 80)

#!/usr/bin/env python3
"""
Test the custom dependency nodes that can be used in the UI.

Run with: ./.venv/bin/python3 test_custom_dependency_nodes.py
"""

import sys
import os

# Add custom node path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'custom_nodes', 'comfy_dependency_nodes'))

from dependency_nodes import (
    NODE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS,
    AddDependencyInput,
    AddDependencyIO,
    DependencyBarrier,
    DependencySignal,
    DependencyMerge,
    WaitFor,
)

print("=" * 80)
print("Testing Custom Dependency Nodes for UI")
print("=" * 80)

# Test node registration
print("\n[Test 1] Node Registration")
print("-" * 80)
print(f"Registered nodes: {list(NODE_CLASS_MAPPINGS.keys())}")
assert len(NODE_CLASS_MAPPINGS) == 6, f"Should have 6 nodes, got {len(NODE_CLASS_MAPPINGS)}"
assert len(NODE_DISPLAY_NAME_MAPPINGS) == 6, "Should have 6 display names"
print("✓ All nodes registered correctly")

# Test AddDependencyInput
print("\n[Test 2] AddDependencyInput")
print("-" * 80)
node = AddDependencyInput()
input_types = node.INPUT_TYPES()
print(f"INPUT_TYPES: {input_types}")
assert "value" in input_types["required"], "Should have required value input"
assert "depends_on" in input_types["optional"], "Should have optional depends_on input"

result = node.passthrough(value="test_data", depends_on="ignored")
assert result == ("test_data",), f"Expected ('test_data',), got {result}"
print("✓ AddDependencyInput works")

# Test AddDependencyIO
print("\n[Test 3] AddDependencyIO")
print("-" * 80)
node = AddDependencyIO()
input_types = node.INPUT_TYPES()
assert "value" in input_types["required"], "Should have required value input"
assert "depends_on" in input_types["optional"], "Should have optional depends_on input"
assert node.RETURN_TYPES == ("*", "*"), "Should return 2 ANY types"
assert node.RETURN_NAMES == ("value", "signal_out"), "Should have correct return names"

result = node.passthrough_with_signal(value="data", depends_on="signal")
assert result == ("data", "signal"), f"Expected ('data', 'signal'), got {result}"
print("✓ AddDependencyIO works")

# Test DependencyBarrier
print("\n[Test 4] DependencyBarrier")
print("-" * 80)
node = DependencyBarrier()
input_types = node.INPUT_TYPES()
assert "value" in input_types["required"], "Should have required value input"
assert "dep1" in input_types["optional"], "Should have dep1"
assert "dep10" in input_types["optional"], "Should have dep10"

result = node.barrier(
    value="main_data",
    dep1="node1",
    dep2="node2",
    dep3="node3",
)
assert result == ("main_data",), f"Expected ('main_data',), got {result}"
print("✓ DependencyBarrier works")

# Test DependencySignal
print("\n[Test 5] DependencySignal")
print("-" * 80)
node = DependencySignal()

# Test empty signal
result = node.generate_signal(signal_type="empty")
assert result == (None,), f"Expected (None,), got {result}"
print("  ✓ Empty signal works")

# Test counter signal
result = node.generate_signal(signal_type="counter", counter_value=42)
assert result == (42,), f"Expected (42,), got {result}"
print("  ✓ Counter signal works")

# Test message signal
result = node.generate_signal(signal_type="message", message="test_msg")
assert result == ("test_msg",), f"Expected ('test_msg',), got {result}"
print("  ✓ Message signal works")

# Test timestamp signal
result = node.generate_signal(signal_type="timestamp")
assert isinstance(result[0], float), "Timestamp should be a float"
print(f"  ✓ Timestamp signal works: {result[0]}")

print("✓ DependencySignal works")

# Test DependencyMerge
print("\n[Test 6] DependencyMerge")
print("-" * 80)
node = DependencyMerge()
input_types = node.INPUT_TYPES()
assert "data1" in input_types["required"], "Should have data1"
assert "data2" in input_types["optional"], "Should have data2"
assert "dep1" in input_types["optional"], "Should have dep1"

result = node.merge(
    data1="first",
    data2="second",
    data3="third",
    dep1="wait1",
    dep2="wait2",
)
assert result == ("first", "second", "third", None), f"Expected 4 values, got {result}"
print("✓ DependencyMerge works")

# Test WaitFor
print("\n[Test 7] WaitFor")
print("-" * 80)
node = WaitFor()
input_types = node.INPUT_TYPES()
assert "value" in input_types["required"], "Should have value"
assert "wait_for" in input_types["required"], "Should have wait_for (required!)"

result = node.wait(value="data", wait_for="signal")
assert result == ("data",), f"Expected ('data',), got {result}"
print("✓ WaitFor works")

# Test workflow simulation
print("\n[Test 8] Workflow Simulation")
print("-" * 80)

# Simulate: NodeA → AddDependencyIO → NodeB → AddDependencyIO → NodeC
print("Simulating chained workflow:")

add_io1 = AddDependencyIO()
add_io2 = AddDependencyIO()

# Step 1: NodeA output goes through first AddDependencyIO
step1 = add_io1.passthrough_with_signal(value="A_result", depends_on="start")
print(f"  Step 1: {step1}")
assert step1 == ("A_result", "start"), "Step 1 failed"

# Step 2: NodeB takes A's result, signal propagates
step2 = add_io2.passthrough_with_signal(value="B_result", depends_on=step1[1])
print(f"  Step 2: {step2}")
assert step2 == ("B_result", "start"), "Step 2 failed"

# Step 3: NodeC receives final signal
final_result = step2[1]
print(f"  Final signal: {final_result}")
assert final_result == "start", "Signal should propagate through chain"

print("✓ Chained workflow simulation works")

# Summary
print("\n" + "=" * 80)
print("ALL CUSTOM NODE TESTS PASSED! ✓")
print("=" * 80)
print("\nThe custom dependency nodes are ready for UI use!")
print("\nTo use in ComfyUI:")
print("  1. Restart ComfyUI")
print("  2. Look for nodes in 'utils/dependencies' category")
print("  3. Add them to your workflow")
print("  4. Connect dependency inputs to control execution order")
print("\nAvailable nodes:")
for node_id, display_name in NODE_DISPLAY_NAME_MAPPINGS.items():
    print(f"  • {display_name}")
print("=" * 80)

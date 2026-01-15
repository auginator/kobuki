#!/usr/bin/env python3
"""
Helper script to save SLAM maps interactively.
Run this in a separate terminal while mapping is active.
"""

import sys
from datetime import datetime

def main():
    from slam_toolbox.srv import SerializePoseGraph, SaveMap
    import rclpy
    from rclpy.node import Node

    rclpy.init()
    node = Node('map_saver')

    serialize_client = node.create_client(SerializePoseGraph, '/slam_toolbox/serialize_map')
    save_map_client = node.create_client(SaveMap, '/slam_toolbox/save_map')

    print("\nWaiting for SLAM toolbox services...")
    if not serialize_client.wait_for_service(timeout_sec=5.0):
        print("ERROR: SLAM toolbox not running!")
        sys.exit(1)

    print("\n" + "="*60)
    print("SAVE SLAM MAP")
    print("="*60)

    map_name = input("\nEnter map name (default: map_YYYYMMDD_HHMMSS): ").strip()
    if not map_name:
        map_name = f"map_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    full_path = f"/ros2_ws/maps/{map_name}"

    print(f"\nSaving map as: {full_path}")

    # Save posegraph
    req = SerializePoseGraph.Request()
    req.filename = full_path
    future = serialize_client.call_async(req)
    rclpy.spin_until_future_complete(node, future, timeout_sec=5.0)

    if future.result():
        print(f"✓ Saved: {full_path}.posegraph")
    else:
        print("✗ Failed to save posegraph")
        sys.exit(1)

    # Save ROS map
    req = SaveMap.Request()
    req.name.data = full_path
    future = save_map_client.call_async(req)
    rclpy.spin_until_future_complete(node, future, timeout_sec=5.0)

    if future.result():
        print(f"✓ Saved: {full_path}.yaml/.pgm")
    else:
        print("✗ Failed to save ROS map")

    print("\n" + "="*60)
    print("Map saved successfully!")
    print("="*60 + "\n")

    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

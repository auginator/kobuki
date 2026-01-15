#!/usr/bin/env python3
"""
Interactive SLAM mapping controller.

Allows users to:
- Press 's' to save the map
- Press 'q' to quit mapping
"""

import rclpy
from rclpy.node import Node
from slam_toolbox.srv import SerializePoseGraph, SaveMap
import sys
import select
import termios
import tty
import os
from datetime import datetime


class SlamMappingController(Node):
    def __init__(self):
        super().__init__('slam_mapping_controller')
        
        # Create service clients
        self.serialize_client = self.create_client(
            SerializePoseGraph, '/slam_toolbox/serialize_map')
        self.save_map_client = self.create_client(
            SaveMap, '/slam_toolbox/save_map')
        
        # Wait for services
        self.get_logger().info('Waiting for SLAM toolbox services...')
        while not self.serialize_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('Waiting for /slam_toolbox/serialize_map service...')
        while not self.save_map_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('Waiting for /slam_toolbox/save_map service...')
        
        self.get_logger().info('SLAM Toolbox services ready!')
        
        # Terminal settings
        self.settings = None
        
    def save_map(self, map_name):
        """Save the map in both SLAM toolbox and standard ROS formats."""
        self.get_logger().info(f'Saving map as: {map_name}')
        
        # Save as SLAM toolbox posegraph format
        serialize_req = SerializePoseGraph.Request()
        serialize_req.filename = map_name
        
        serialize_future = self.serialize_client.call_async(serialize_req)
        rclpy.spin_until_future_complete(self, serialize_future, timeout_sec=5.0)
        
        if serialize_future.result() is not None:
            self.get_logger().info(f'✓ Saved posegraph: {map_name}.posegraph')
        else:
            self.get_logger().error('Failed to save posegraph')
            return False
        
        # Save as standard ROS map format (.yaml/.pgm)
        save_map_req = SaveMap.Request()
        save_map_req.name.data = map_name
        
        save_future = self.save_map_client.call_async(save_map_req)
        rclpy.spin_until_future_complete(self, save_future, timeout_sec=5.0)
        
        if save_future.result() is not None:
            self.get_logger().info(f'✓ Saved ROS map: {map_name}.yaml/.pgm')
        else:
            self.get_logger().error('Failed to save ROS map')
            return False
        
        self.get_logger().info('✓ Map saved successfully!')
        return True
    
    def get_keypress(self):
        """Get a single keypress without blocking."""
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1)
        return None
    
    def run_interactive(self):
        """Run the interactive controller."""
        print("\n" + "="*60)
        print("SLAM MAPPING CONTROLLER")
        print("="*60)
        print("\nCommands:")
        print("  's' - Save the current map")
        print("  'q' - Quit mapping")
        print("\nMapping is now active. Drive the robot to build the map.")
        print("View the map in Foxglove on the /map topic.")
        print("="*60 + "\n")
        
        # Set terminal to raw mode for single character input
        self.settings = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())
        
        try:
            while rclpy.ok():
                # Check for keypress
                key = self.get_keypress()
                
                if key == 's':
                    print("\r\n")
                    # Switch back to normal mode for input
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.settings)
                    
                    map_name = input("Enter map name (default: map_YYYYMMDD_HHMMSS): ").strip()
                    if not map_name:
                        map_name = f"map_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    
                    # Add full path
                    full_path = f"/ros2_ws/maps/{map_name}"
                    self.save_map(full_path)
                    
                    print("\nPress 's' to save again, 'q' to quit\n")
                    
                    # Back to raw mode
                    tty.setraw(sys.stdin.fileno())
                
                elif key == 'q':
                    print("\r\nQuitting mapping...\n")
                    break
                
                # Small sleep to prevent CPU spinning
                rclpy.spin_once(self, timeout_sec=0.1)
        
        finally:
            # Restore terminal settings
            if self.settings:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.settings)


def main(args=None):
    rclpy.init(args=args)
    
    controller = SlamMappingController()
    
    try:
        controller.run_interactive()
    except KeyboardInterrupt:
        pass
    finally:
        controller.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

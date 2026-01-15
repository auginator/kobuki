#!/usr/bin/env python3
"""
SLAM mapping status display.

Displays information about SLAM mapping and available services.
"""

import rclpy
from rclpy.node import Node
from slam_toolbox.srv import SerializePoseGraph, SaveMap


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

    def display_instructions(self):
        """Display mapping instructions and available commands."""
        print("\n" + "="*70)
        print("SLAM MAPPING ACTIVE")
        print("="*70)
        print("\nMapping is now running. Drive the robot to build the map.")
        print("View the map in Foxglove on the /map topic.")
        print("\n" + "-"*70)
        print("TO SAVE A MAP, open a new terminal and run:")
        print("-"*70)
        print("\n  # Save with auto-generated name:")
        print("  ros2 service call /slam_toolbox/serialize_map \\")
        print("    slam_toolbox/srv/SerializePoseGraph \\")
        print("    \"{filename: '/ros2_ws/maps/my_map'}\"")
        print("\n  # Or use the helper script:")
        print("  docker exec -it <container_name> bash")
        print("  python3 /ros2_ws/src/slam/scripts/save_map_helper.py")
        print("\n" + "-"*70)
        print("Press Ctrl+C to stop mapping")
        print("="*70 + "\n")

    def run(self):
        """Run the controller - just display info and keep node alive."""
        self.display_instructions()

        # Just spin to keep the node alive and display status
        try:
            rclpy.spin(self)
        except KeyboardInterrupt:
            self.get_logger().info('Mapping stopped by user')


def main(args=None):
    rclpy.init(args=args)

    controller = SlamMappingController()

    try:
        controller.run()
    except KeyboardInterrupt:
        pass
    finally:
        controller.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

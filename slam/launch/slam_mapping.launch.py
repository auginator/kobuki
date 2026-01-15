#!/usr/bin/env python3
"""
Launch file for interactive SLAM mapping.

Starts SLAM Toolbox in mapping mode with an interactive controller
that allows users to save maps and control the mapping process.
"""

import os
from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, Command, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # Get the package directory
    slam_pkg_dir = get_package_share_directory('slam')

    # Declare launch arguments
    use_sim_time = LaunchConfiguration('use_sim_time')

    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='Use simulation (Gazebo) clock if true'
    )

    # Robot description for robot_state_publisher
    urdf_model = PathJoinSubstitution(
        [FindPackageShare('kobuki_description'),
         'urdf', 'kobuki_standalone.urdf.xacro']
    )

    robot_description_param = {
        'robot_description': Command(['xacro ', urdf_model]),
        'use_sim_time': use_sim_time
    }

    # robot_state_publisher publishes TFs from the URDF (base_footprint -> base_link, camera_link, etc.)
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[robot_description_param]
    )

    # joint_state_publisher for non-fixed joints
    joint_state_publisher = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}]
    )

    # SLAM Toolbox node in async mapping mode
    slam_toolbox_node = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[
            os.path.join(slam_pkg_dir, 'config', 'mapper_params_online_async.yaml'),
            {'use_sim_time': use_sim_time}
        ],
    )

    # Interactive mapping controller
    slam_controller = Node(
        package='slam',
        executable='slam_controller.py',
        name='slam_mapping_controller',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}],
    )

    ld = LaunchDescription()

    # Add launch arguments
    ld.add_action(declare_use_sim_time)

    # Add robot description nodes
    ld.add_action(robot_state_publisher)
    ld.add_action(joint_state_publisher)

    # Add nodes
    ld.add_action(slam_toolbox_node)
    ld.add_action(slam_controller)

    return ld

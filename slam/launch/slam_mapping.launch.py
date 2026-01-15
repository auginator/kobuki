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
from launch.substitutions import LaunchConfiguration


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
        prefix='xterm -e',  # Run in separate terminal for interactivity
    )
    
    ld = LaunchDescription()
    
    # Add launch arguments
    ld.add_action(declare_use_sim_time)
    
    # Add nodes
    ld.add_action(slam_toolbox_node)
    ld.add_action(slam_controller)
    
    return ld

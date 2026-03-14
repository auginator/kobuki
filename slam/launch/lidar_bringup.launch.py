#!/usr/bin/env python3
"""
Top-level bringup launch for the lidar_node container.
Starts the lidar driver (with TF and Foxglove bridge) and the launch agent.
"""

import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    slam_pkg_dir = get_package_share_directory('slam')

    lidar_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(slam_pkg_dir, 'launch', 'sllidar_with_transform.launch.py')
        )
    )

    launch_agent = Node(
        package='slam',
        executable='launch_agent_node.py',
        name='launch_agent',
        output='screen',
    )

    return LaunchDescription([
        lidar_launch,
        launch_agent,
    ])

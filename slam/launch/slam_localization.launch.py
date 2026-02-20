#!/usr/bin/env python3
"""
Launch file for SLAM localization.

Launches SLAM Toolbox in localization mode with a specified map.
"""

import os
from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration


def launch_setup(context, *args, **kwargs):
    """Setup function to launch SLAM Toolbox in localization mode."""

    # Get the package directory
    slam_pkg_dir = get_package_share_directory('slam')

    # Get launch configuration
    use_sim_time = LaunchConfiguration('use_sim_time')
    map_file_arg = LaunchConfiguration('map_file')

    # Get map file from launch argument
    map_file = map_file_arg.perform(context)

    # Error if no map file provided
    if not map_file or map_file == '':
        raise RuntimeError(
            "No map file specified. Please provide a map file using: "
            "map_file:=<path_to_map>"
        )

    print(f"\n✓ Loading map: {map_file}\n")

    # SLAM Toolbox node in localization mode
    slam_toolbox_node = Node(
        package='slam_toolbox',
        executable='localization_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[
            os.path.join(slam_pkg_dir, 'config',
                         'mapper_params_localization.yaml'),
            {
                'use_sim_time': use_sim_time,
                'map_file_name': map_file,
                'map_start_at_dock': True
            }
        ],
    )

    return [slam_toolbox_node]


def generate_launch_description():
    # Declare launch arguments
    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='Use simulation (Gazebo) clock if true'
    )

    declare_map_file = DeclareLaunchArgument(
        'map_file',
        default_value='',
        description='Full path to the map file to load (required)'
    )

    ld = LaunchDescription()

    # Add launch arguments
    ld.add_action(declare_use_sim_time)
    ld.add_action(declare_map_file)

    # Add opaque function for map selection and node launching
    ld.add_action(OpaqueFunction(function=launch_setup))

    return ld

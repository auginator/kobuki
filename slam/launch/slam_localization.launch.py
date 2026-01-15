#!/usr/bin/env python3
"""
Launch file for interactive SLAM localization.

Allows user to select a map from available maps and launches
SLAM Toolbox in localization mode.
"""

import os
import sys
import subprocess
from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration


def launch_setup(context, *args, **kwargs):
    """Setup function to run map selection before launching nodes."""

    # Get the package directory
    slam_pkg_dir = get_package_share_directory('slam')

    # Get launch configuration
    use_sim_time = LaunchConfiguration('use_sim_time')
    map_file_arg = LaunchConfiguration('map_file')

    # Try to get map file from launch argument
    map_file = map_file_arg.perform(context)

    # If no map file provided, run interactive selector
    if not map_file or map_file == '':
        print("\n" + "="*70)
        print("No map file specified. Running interactive map selector...")
        print("="*70)

        # Run the map selector script
        selector_script = os.path.join(slam_pkg_dir, 'scripts', 'map_selector.py')

        try:
            result = subprocess.run(
                ['python3', selector_script],
                capture_output=True,
                text=True,
                check=True
            )

            # Parse output to get selected map file
            for line in result.stdout.split('\n'):
                if line.startswith('MAP_FILE='):
                    map_file = line.split('=', 1)[1].strip()
                    break

            if not map_file:
                print("No map selected. Exiting...")
                sys.exit(1)

        except subprocess.CalledProcessError:
            print("Map selection cancelled or failed. Exiting...")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nMap selection cancelled. Exiting...")
            sys.exit(1)

    print(f"\n✓ Loading map: {map_file}\n")

    # SLAM Toolbox node in localization mode
    slam_toolbox_node = Node(
        package='slam_toolbox',
        executable='localization_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[
            os.path.join(slam_pkg_dir, 'config', 'mapper_params_localization.yaml'),
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
        description='Full path to the map file to load (empty for interactive selection)'
    )

    ld = LaunchDescription()

    # Add launch arguments
    ld.add_action(declare_use_sim_time)
    ld.add_action(declare_map_file)

    # Add opaque function for map selection and node launching
    ld.add_action(OpaqueFunction(function=launch_setup))

    return ld

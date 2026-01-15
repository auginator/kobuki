import os
from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():

    # Include the sllidar_ros2 launch file
    sllidar_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory(
                'sllidar_ros2'), 'launch', 'sllidar_c1_launch.py')
        )
    )

    # Static transform from base_footprint to base_link (robot geometry)
    base_footprint_to_base_link = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='base_footprint_to_base_link',
        arguments=['--x', '0', '--y', '0', '--z', '0.01',
                   '--roll', '0', '--pitch', '0', '--yaw', '0',
                   '--frame-id', 'base_footprint', '--child-frame-id', 'base_link'],
        output='screen'
    )

    # Static transform publisher from base_link to laser (sensor mounting)
    base_link_to_laser = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='base_link_to_laser_transform',
        arguments=['--x', '0', '--y', '0', '--z', '0.1',
                   '--roll', '0', '--pitch', '0', '--yaw', '3.14159',
                   '--frame-id', 'base_link', '--child-frame-id', 'laser'],
        output='screen'
    )

    # Foxglove bridge
    foxglove_bridge = Node(
        package='foxglove_bridge',
        executable='foxglove_bridge',
        name='foxglove_bridge',
        output='screen'
    )

    ld = LaunchDescription()

    ld.add_action(sllidar_launch)
    ld.add_action(base_footprint_to_base_link)
    ld.add_action(base_link_to_laser)
    ld.add_action(foxglove_bridge)

    return ld

import os
from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():

    # Include the original kobuki_node launch file
    kobuki_node_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory(
                'kobuki_node'), 'launch', 'kobuki_node.launch.py')
        )
    )

    # Add the kobuki_description launch file
    kobuki_description_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory(
                'kobuki_description'), 'launch', 'kobuki_description.launch.py')
        )
    )

    # Static transform publisher from base_link to laser
    static_transform_publisher = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='base_link_to_laser_transform',
        arguments=['--x', '0', '--y', '0', '--z', '0',
                   '--roll', '0', '--pitch', '0', '--yaw', '0',
                   '--frame-id', 'base_link', '--child-frame-id', 'laser'],
        output='screen'
    )

    ld = LaunchDescription()

    ld.add_action(kobuki_node_launch)
    ld.add_action(kobuki_description_launch)
    ld.add_action(static_transform_publisher)

    return ld

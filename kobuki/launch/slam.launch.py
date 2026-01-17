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

    ld = LaunchDescription()

    ld.add_action(sllidar_launch)

    return ld

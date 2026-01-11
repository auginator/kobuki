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
        ),
        launch_arguments={
            'use_rviz': 'False',
            'use_sim_time': 'False'
        }.items()
    )

    ld = LaunchDescription()

    ld.add_action(kobuki_node_launch)
    ld.add_action(kobuki_description_launch)

    return ld

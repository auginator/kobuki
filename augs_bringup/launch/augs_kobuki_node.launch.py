import os
from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():

    # Robot description. Uses a repo-local URDF (augs_bringup/urdf/kobuki_augs.urdf.xacro)
    # that owns base_footprint -> base_link in the correct direction. This replaces the
    # stock kobuki_description URDF (which published base_link -> base_footprint backwards)
    # and the separate static_transform_publisher we used to patch around it, both of which
    # together created a TF tree cycle. base_footprint is the URDF root; kobuki_node supplies
    # odom -> base_footprint.
    urdf_path = os.path.join(
        get_package_share_directory('augs_bringup'),
        'urdf', 'kobuki_augs.urdf.xacro')

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'use_sim_time': False,
            'robot_description': ParameterValue(
                Command(['xacro ', urdf_path]), value_type=str),
        }]
    )

    # Include the original kobuki_node launch file (publishes odom -> base_footprint)
    kobuki_node_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory(
                'kobuki_node'), 'launch', 'kobuki_node.launch.py')
        )
    )

    ld = LaunchDescription()

    ld.add_action(robot_state_publisher)
    ld.add_action(kobuki_node_launch)

    return ld

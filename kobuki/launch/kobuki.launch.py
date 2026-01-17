import os
from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import ExecuteProcess, DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, Command, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():

    ## Static transform: base_footprint -> base_link (10.2mm vertical offset)
    # Note: The URDF has this backwards (base_link->base_footprint), but since kobuki_node
    # publishes odom->base_footprint, we need the correct direction here
    base_footprint_to_base_link = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='base_footprint_to_base_link',
        arguments=['0', '0', '0.0102', '0', '0', '0', 'base_footprint', 'base_link'],
        output='screen'
    )

    ## Robot Description (URDF) - provides static transforms for sensor/wheel links
    robot_description_param = {
        'robot_description': Command(['xacro ', PathJoinSubstitution(
            [FindPackageShare('kobuki_description'), 'urdf', 'kobuki_standalone.urdf.xacro']
        )])}

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[robot_description_param, {'publish_root_tf': False}]  # Don't publish base_link->base_footprint
    )

    ## Start the kobuki node to establish connectivity with robot

    kobuki_node_launch    = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(get_package_share_directory('kobuki_node'), 'launch', 'kobuki_node_mux.launch.py')),
        launch_arguments={'publish_tf': 'true'}.items()
    )

    ## Start the joystick keyop to establish connectivity with joystick controller

    kobuki_joyop_launch   = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(get_package_share_directory('kobuki_joyop'), 'launch', 'kobuki_joyop_mux.launch.py'))
    )

    ## Start the cmd_vel_mux

    cmd_vel_mux_launch   = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(get_package_share_directory('cmd_vel_mux'), 'launch', 'cmd_vel_mux.launch.py'))
    )

    ld = LaunchDescription()

    ld.add_action(base_footprint_to_base_link)
    ld.add_action(robot_state_publisher)
    ld.add_action(kobuki_node_launch)
    ld.add_action(kobuki_joyop_launch)
    ld.add_action(cmd_vel_mux_launch)

    return ld
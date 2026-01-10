from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # Allow overriding the URDF/xacro file on the command line
    urdf_arg = DeclareLaunchArgument(
        'urdf_model',
        default_value=PathJoinSubstitution(
            [FindPackageShare('kobuki_description'),
             'urdf', 'kobuki.urdf.xacro']
        ),
        description='Path to robot xacro/urdf file'
    )

    urdf_model = LaunchConfiguration('urdf_model')

    # Run xacro on the file and pass the resulting URDF text as the robot_description parameter
    robot_description_param = {
        'robot_description': Command(['xacro ', urdf_model])}

    # robot_state_publisher publishes TFs from the robot_description
    rsp_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[robot_description_param]
    )

    # joint_state_publisher publishes joint states (use joint_state_publisher_gui if you want a GUI)
    jsp_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        output='screen'
    )

    return LaunchDescription([
        urdf_arg,
        rsp_node,
        jsp_node,
    ])

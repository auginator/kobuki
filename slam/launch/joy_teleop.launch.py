from launch import LaunchDescription
from launch_ros.actions import Node
import os
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    config = os.path.join(
        get_package_share_directory('slam'),
        'config',
        'ps4.config.yaml'
    )

    return LaunchDescription([
        Node(
            package='joy',
            executable='joy_node',
            name='joy_node',
            parameters=[{'dev': '/dev/input/js0'}]
        ),
        Node(
            package='teleop_twist_joy',
            executable='teleop_node',
            name='teleop_twist_joy_node',
            parameters=[config],
            # Publish into the cmd_vel_mux joystick input (priority 10) so the
            # joystick preempts autonomous motion instead of dogpiling /cmd_vel.
            remappings=[('cmd_vel', '/mux/input/joystick')],
        ),
    ])

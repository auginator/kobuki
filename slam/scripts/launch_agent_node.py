#!/usr/bin/env python3
"""
Launch Agent Node
=================
A ROS2 node that manages launch file subprocesses on behalf of remote callers.
Exposes start/stop/status services so the orchestrator can control launch files
running inside this container without needing the packages installed locally.
"""

import os
import signal
import subprocess

import rclpy
from rclpy.node import Node

from launch_agent_interfaces.srv import LaunchStart, LaunchStop, LaunchStatus


class LaunchAgentNode(Node):

    def __init__(self):
        super().__init__('launch_agent')
        self._processes: dict[str, subprocess.Popen] = {}

        self.create_service(LaunchStart, 'launch_agent/start', self._handle_start)
        self.create_service(LaunchStop, 'launch_agent/stop', self._handle_stop)
        self.create_service(LaunchStatus, 'launch_agent/status', self._handle_status)

        self.get_logger().info('Launch agent ready')

    def _handle_start(self, request, response):
        key = request.key
        pkg = request.launch_package
        launch_file = request.launch_file
        extra_args = list(request.extra_args)

        self.get_logger().info(
            f'Start requested: key={key} pkg={pkg} file={launch_file} args={extra_args}'
        )

        # Kill any existing process under this key
        self._kill(key)

        cmd = ['ros2', 'launch', pkg, launch_file] + extra_args
        try:
            proc = subprocess.Popen(
                cmd,
                preexec_fn=os.setsid,
            )
            self._processes[key] = proc
            response.success = True
            response.message = f'Launched [{key}] (pid {proc.pid})'
            response.pid = proc.pid
            self.get_logger().info(f'Launched [{key}] pid={proc.pid}: {" ".join(cmd)}')
        except Exception as e:
            response.success = False
            response.message = f'Failed to launch [{key}]: {e}'
            response.pid = 0
            self.get_logger().error(f'Failed to launch [{key}]: {e}')

        return response

    def _handle_stop(self, request, response):
        key = request.key
        self.get_logger().info(f'Stop requested: key={key}')

        proc = self._processes.get(key)
        if proc is None or proc.poll() is not None:
            self._processes.pop(key, None)
            response.success = True
            response.message = f'[{key}] not running'
            return response

        self._kill(key)
        response.success = True
        response.message = f'[{key}] stopped'
        return response

    def _handle_status(self, request, response):
        if request.key:
            keys_to_check = [request.key] if request.key in self._processes else []
        else:
            keys_to_check = list(self._processes.keys())

        response.keys = []
        response.running = []
        response.pids = []

        for key in keys_to_check:
            proc = self._processes[key]
            running = proc.poll() is None
            response.keys.append(key)
            response.running.append(running)
            response.pids.append(proc.pid if running else 0)

        return response

    def _kill(self, key: str):
        proc = self._processes.pop(key, None)
        if proc and proc.poll() is None:
            self.get_logger().info(f'Terminating [{key}] (pid {proc.pid})')
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                proc.wait(timeout=10)
            except Exception as e:
                self.get_logger().warning(f'Error killing [{key}]: {e}')
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    pass

    def _kill_all(self):
        for key in list(self._processes.keys()):
            self._kill(key)

    def destroy_node(self):
        self.get_logger().info('Shutting down launch agent, killing all children')
        self._kill_all()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = LaunchAgentNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

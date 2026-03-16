# Lessons Learned

Accumulated knowledge from building and debugging the Kobuki robot orchestrator system.

## ROS2 + Python Threading

### rclpy cannot be spun from multiple threads

When `rclpy.spin(node)` runs in a background thread (e.g. for FastAPI coexistence), you **cannot** call `rclpy.spin_until_future_complete()`, `client.wait_for_service()`, or `client.service_is_ready()` from another thread. The executor's graph guard condition only fires in the spin thread.

**Pattern that works:** Fire `client.call_async(request)` and poll `future.done()` in a sleep loop. The background spin thread resolves the future.

```python
def _wait_for_future(self, future, timeout: float):
    end = time.time() + timeout
    while not future.done() and time.time() < end:
        time.sleep(0.05)
    if not future.done():
        future.cancel()
        return None
    return future.result()
```

Skip `wait_for_service` entirely — just fire the request and let it time out naturally via Zenoh.

### ROS2 logger does not support printf-style args

`self.get_logger().info()` (RcutilsLogger) takes a single string. It does **not** support `%s` positional arguments like Python's `logging` module.

```python
# WRONG — crashes with TypeError
self.get_logger().info('key=%s pkg=%s', key, pkg)

# CORRECT
self.get_logger().info(f'key={key} pkg={pkg}')
```

## Docker / Container Architecture

### Packages must be installed where they run

`ros2 launch` resolves packages locally. If the orchestrator container calls `ros2 launch slam ...` but the `slam` package only exists in `lidar_node`, it fails with "Package not found." Launch files must execute in the container that has the packages installed.

**Solution:** The launch agent pattern — a ROS2 node inside `lidar_node` that accepts start/stop service calls over Zenoh, managing subprocesses locally.

### Subprocess pipes can silently kill child processes

Using `stdout=subprocess.PIPE` without reading the pipe causes the buffer to fill. The child process blocks on write and appears to "die silently." Remove pipe arguments so children inherit stdio and logs flow to `docker logs`.

### Zenoh config must match across all containers

If one container uses `zenoh_config.json5` and another uses `zenoh_config_no_shm.json5`, they may have different discovery settings and fail to find each other's services. All containers in the compose network should use the same Zenoh config. The orchestrator needs `privileged: true` for Zenoh SHM.

## Nav2

### nav2_bringup must be installed in the launching container

Nav2 packages are heavy. Only install `ros-humble-nav2-bringup` in the container that actually runs the Nav2 launch file (lidar_node). The orchestrator only needs `ros-humble-nav2-msgs` for the `NavigateToPose` action type.

### Nav2 lifecycle nodes take time to start

After launching Nav2, the action server (`/navigate_to_pose`) is not immediately available. The lifecycle manager must transition all nodes (controller_server, planner_server, bt_navigator, etc.) through unconfigured → inactive → active. This can take 10-30 seconds. Query lifecycle state via `lifecycle_msgs/srv/GetState` to know when it's ready.

### NavigateToPose action server availability

The `wait_for_server()` call on the action client has the same threading limitation as service calls — it may not work reliably from a non-spin thread. Use the poll-based `_wait_for_future` pattern for `send_goal_async` as well.

## General Debugging

### Check if the service actually exists before debugging the client

When service calls fail, first verify the service exists with `ros2 service list` from inside the container. During one debugging session, we spent time investigating client-side threading issues when the real problem was the lidar_node container was down.

### Dockerfile layer ordering matters for iteration speed

Put frequently-changing layers (like `COPY orchestrator/robot_orchestrator.py`) as late as possible. Put slow layers (like `apt-get install` and `colcon build`) early so they're cached. The orchestrator Dockerfile copies the Python file last so code changes don't trigger a full rebuild.

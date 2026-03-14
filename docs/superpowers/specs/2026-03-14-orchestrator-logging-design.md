# Orchestrator Logging Improvements

**Date:** 2026-03-14
**File:** `orchestrator/robot_orchestrator.py`

## Problem

1. **Child subprocess logs are invisible.** `_ros2_launch` uses `stdout=subprocess.PIPE, stderr=subprocess.STDOUT` but nothing reads from the pipe. The buffer fills, the child blocks/dies, and no output reaches `docker logs`.
2. **Orchestrator logs not on `/rosout`.** Python `log.info(...)` calls only go to console. They are invisible to Foxglove or any ROS tooling watching `/rosout`.

## Solution

### Change 1: Stream child logs to Docker

Remove `stdout` and `stderr` arguments from the `subprocess.Popen` call in `RobotState._ros2_launch`. Children inherit the orchestrator's stdio file descriptors, so their output flows directly to Docker's log driver.

**Before:**
```python
proc = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    preexec_fn=os.setsid,
)
```

**After:**
```python
proc = subprocess.Popen(
    cmd,
    preexec_fn=os.setsid,
)
```

### Change 2: Bridge Python logging to `/rosout`

Add a `RosoutHandler(logging.Handler)` class that forwards Python log records to the ROS node logger.

**Level mapping:**
| Python level | ROS logger method |
|---|---|
| `DEBUG` | `get_logger().debug()` |
| `INFO` | `get_logger().info()` |
| `WARNING` | `get_logger().warn()` |
| `ERROR`, `CRITICAL` | `get_logger().error()` |

**Lifecycle:**
- Handler is created and attached to the `"orchestrator"` Python logger inside `lifespan()`, after `ros_node` is initialized.
- Handler is removed inside `lifespan()` shutdown, before `rclpy.shutdown()`.

**Behavior:**
- All existing `log.info(...)` / `log.warning(...)` / etc. calls emit to both console (unchanged) AND `/rosout` (new).
- No call-site changes needed.

## Files Changed

- `orchestrator/robot_orchestrator.py` (only file)

## What Is NOT Changing

- No new dependencies
- No new files
- No changes to Dockerfile or compose.yaml
- No changes to API routes or state machine

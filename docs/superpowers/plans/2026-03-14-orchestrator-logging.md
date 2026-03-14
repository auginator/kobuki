# Orchestrator Logging Improvements Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make child subprocess logs visible in `docker logs` and bridge Python logging to ROS `/rosout`.

**Architecture:** Remove subprocess pipe capture so children inherit stdio (Docker captures it). Add a `logging.Handler` subclass that forwards Python log records to `ros_node.get_logger()`, attached during FastAPI lifespan.

**Tech Stack:** Python `logging`, `subprocess`, `rclpy`

**Spec:** `docs/superpowers/specs/2026-03-14-orchestrator-logging-design.md`

---

## File Structure

- Modify: `orchestrator/robot_orchestrator.py` — only file changed

No new files. No test files (ROS dependencies not available on host machine per CLAUDE.md).

---

## Chunk 1: Both Changes

### Task 1: Remove subprocess pipe capture

**Files:**
- Modify: `orchestrator/robot_orchestrator.py:113-118`

- [ ] **Step 1: Remove stdout/stderr pipe arguments from `_ros2_launch`**

In `RobotState._ros2_launch`, change the `subprocess.Popen` call from:

```python
proc = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    preexec_fn=os.setsid,
)
```

To:

```python
proc = subprocess.Popen(
    cmd,
    preexec_fn=os.setsid,
)
```

- [ ] **Step 2: Commit**

```bash
git add orchestrator/robot_orchestrator.py
git commit -m "fix: let child subprocess logs flow to docker logs

Remove stdout=PIPE and stderr=STDOUT from _ros2_launch so child
processes inherit the orchestrator's stdio. Previously the pipe
was never read, causing children to block and logs to be lost."
```

---

### Task 2: Add RosoutHandler to bridge Python logging to `/rosout`

**Files:**
- Modify: `orchestrator/robot_orchestrator.py:74` (after logger definition)
- Modify: `orchestrator/robot_orchestrator.py:266-281` (lifespan function)

- [ ] **Step 1: Add the `RosoutHandler` class after the Python logger definition (after line 74)**

Insert after `log = logging.getLogger("orchestrator")`:

```python
class RosoutHandler(logging.Handler):
    """Forward Python log records to the ROS2 node logger (/rosout)."""

    def __init__(self, ros_node_ref):
        super().__init__()
        self._ros_node = ros_node_ref

    def emit(self, record):
        try:
            msg = self.format(record)
            logger = self._ros_node.get_logger()
            if record.levelno >= logging.ERROR:
                logger.error(msg)
            elif record.levelno >= logging.WARNING:
                logger.warn(msg)
            elif record.levelno >= logging.INFO:
                logger.info(msg)
            else:
                logger.debug(msg)
        except Exception:
            self.handleError(record)
```

- [ ] **Step 2: Attach the handler in `lifespan()` after ros_node init, remove on shutdown**

In the `lifespan` function, after `_ros_thread.start()` and the existing `log.info("ROS2 node spinning")`, add:

```python
    rosout_handler = RosoutHandler(ros_node)
    log.addHandler(rosout_handler)
```

In the shutdown section, before `state.kill_all()`, add:

```python
    log.removeHandler(rosout_handler)
```

The full lifespan function should read:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    global ros_node, _ros_thread
    import threading

    rclpy.init()
    ros_node = OrchestratorNode()
    _ros_thread = threading.Thread(target=_spin_ros, daemon=True)
    _ros_thread.start()
    log.info("ROS2 node spinning")

    rosout_handler = RosoutHandler(ros_node)
    log.addHandler(rosout_handler)

    yield

    # Shutdown
    log.info("Shutting down orchestrator")
    log.removeHandler(rosout_handler)
    state.kill_all()
    rclpy.shutdown()
```

- [ ] **Step 3: Commit**

```bash
git add orchestrator/robot_orchestrator.py
git commit -m "feat: bridge Python logging to ROS /rosout

Add RosoutHandler that forwards orchestrator log records to
ros_node.get_logger(), making them visible in Foxglove and
any ROS tooling watching /rosout."
```

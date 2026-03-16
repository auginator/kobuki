# Nav2 Debugging & Integration Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Debug why Nav2 lifecycle nodes fail to reach "active" state and get NavigateToPose working end-to-end.

**Architecture:** Nav2 runs inside the lidar_node container (launched via launch_agent). The orchestrator container communicates over Zenoh. The lifecycle_manager inside nav2_bringup's `navigation_launch.py` is responsible for transitioning nodes through unconfigured → inactive → active. Currently it's failing silently.

**Tech Stack:** ROS2 Humble, Nav2, SLAM Toolbox, Zenoh RMW, Docker, FastAPI

---

## Diagnosis Summary

The `/status` response reveals the root problem:

```json
"nav2_lifecycle": {
    "controller_server": "unavailable",
    "planner_server": "unavailable",
    "bt_navigator": "unavailable",
    "behavior_server": "unconfigured"
}
```

- **"unavailable"** = the orchestrator's `GetState` service call timed out — the node either crashed, hasn't started, or its service isn't reachable via Zenoh.
- **"unconfigured"** = the node exists but the lifecycle_manager hasn't configured it yet (or tried and failed).
- The NavigateToPose action server is hosted by `bt_navigator` — it only becomes available when bt_navigator reaches the **active** lifecycle state.

**Most likely causes (in priority order):**

1. **Lifecycle manager chain stall** — the `nav2_params.yaml` lifecycle_manager lists 6 nodes (controller_server, smoother_server, planner_server, behavior_server, bt_navigator, waypoint_follower). If **any** node in this list crashes or fails to bond, the lifecycle_manager stalls on that node and **never proceeds to configure/activate the remaining nodes**. The orchestrator only monitors 4 of these 6 nodes, so the stall could be caused by smoother_server or waypoint_follower without being visible in `/status`. This is the most likely explanation for the pattern where behavior_server is "unconfigured" (reachable but not yet configured) and the others are "unavailable" (lifecycle services not reachable via Zenoh from orchestrator, likely because they never activated).
2. **Nav2 nodes crashing on startup** — missing TF transforms (`map→odom`), `/map` topic not available, or costmap configuration errors. The global_costmap's `static_layer` has `map_subscribe_transient_local: true`, which expects a transient-local QoS publisher for `/map`. If SLAM Toolbox publishes `/map` with volatile durability (common with Zenoh RMW), the static_layer may never receive the map, blocking costmap initialization.
3. **Zenoh service discovery across containers** — the orchestrator's `GetState` calls go from the orchestrator container to lidar_node container via Zenoh. "unavailable" in `/status` may simply mean Zenoh hasn't discovered those lifecycle service endpoints yet, even if the nodes are healthy inside lidar_node. Nav2's internal communication (lifecycle_manager ↔ nodes) is local within the lidar_node container and should work fine.
4. **Zenoh topic discovery latency** — Nav2's costmaps need `/scan` and `/map` topics from other containers. If Zenoh hasn't connected yet when costmaps initialize, nodes may time out waiting for data.

---

## Chunk 1: Diagnostic Steps (run on robot)

These are manual debugging steps to run on the Raspberry Pi. They require shell access to the running containers. **Do not write code yet — gather data first.**

> **Zenoh environment setup:** All `ros2` CLI commands inside containers require the Zenoh RMW. Run these once per `docker compose exec` session:
> ```bash
> source /opt/ros/humble/setup.bash
> source /ros2_ws/install/setup.bash
> export RMW_IMPLEMENTATION=rmw_zenoh_cpp
> export ZENOH_SESSION_CONFIG_URI=/zenoh_config.json5
> ```

### Task 1: Check Nav2 process logs in lidar_node container

The launch_agent runs `ros2 launch nav2_bringup navigation_launch.py` as a subprocess. Its stdout/stderr go to the launch_agent's console, which means they appear in the lidar_node container logs.

- [ ] **Step 1: Get lidar_node container logs while nav2 is "running"**

```bash
# On the Raspberry Pi — get the lidar_node container name/ID
docker compose logs lidar_node --tail=200 --follow
```

Then trigger nav2 start from the orchestrator API:
```bash
curl -X POST http://<robot-ip>:8080/autonomy/start
```

Watch the logs for errors. **Look for:**
- `[lifecycle_manager]` messages — does it say "Configuring controller_server", "Activating controller_server", or does it report failures?
- `[controller_server]` / `[planner_server]` / `[bt_navigator]` crash messages
- Transform errors: `Could not find a connection between 'map' and 'odom'`
- Costmap errors: `Timed out waiting for transform`, `No map received`

- [ ] **Step 2: Record findings**

Write down the first error(s) that appear. This determines which fix path to take.

### Task 2: Verify TF tree while localization is running

Nav2 requires the transform chain `map → odom → base_footprint`. The SLAM Toolbox localization node publishes `map → odom`. The Kobuki base publishes `odom → base_footprint`.

- [ ] **Step 1: Check TF tree from inside lidar_node container**

```bash
# Exec into the lidar_node container
docker compose exec lidar_node bash

# Inside the container:
source /opt/ros/humble/setup.bash
source /ros2_ws/install/setup.bash
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
export ZENOH_SESSION_CONFIG_URI=/zenoh_config.json5

# Check if the full TF chain exists
ros2 run tf2_ros tf2_echo map base_footprint
```

Expected output: a continuously updating transform. If it says `Could not find...`, the localization isn't publishing `map→odom`.

- [ ] **Step 2: Check the /map topic and its QoS**

```bash
# Inside lidar_node container (same session)
ros2 topic info /map --verbose   # Check publisher QoS (durability, reliability)
ros2 topic echo /map --once      # Check if data arrives
```

If no message arrives within ~10s, SLAM Toolbox localization isn't publishing `/map`. The global_costmap's `static_layer` subscribes to `/map` with `map_subscribe_transient_local: true` — this requires the publisher to use **transient-local** durability QoS. If SLAM Toolbox publishes with **volatile** durability (check the `--verbose` output), the costmap will never receive the map even though the topic exists. This is a known Zenoh RMW issue.

If QoS mismatch is the problem, set `map_subscribe_transient_local: false` in `nav2_params.yaml` for both `global_costmap.static_layer` and `map_saver`.

### Task 3: Verify Nav2 nodes exist (from inside lidar_node)

- [ ] **Step 1: List running lifecycle nodes**

```bash
# Inside lidar_node container
ros2 lifecycle nodes
```

Expected: you should see `/controller_server`, `/planner_server`, `/bt_navigator`, `/behavior_server`, `/smoother_server`, `/waypoint_follower`, `/velocity_smoother`.

If the list is empty or partial, those nodes crashed on startup.

- [ ] **Step 2: Check lifecycle_manager status**

```bash
ros2 lifecycle get /lifecycle_manager_navigation
```

If the lifecycle_manager itself isn't active, the whole chain is stuck.

- [ ] **Step 3: Try manual lifecycle transition**

```bash
# Try configuring a node manually to see the error
ros2 lifecycle set /controller_server configure
```

This will print the actual error if configuration fails (e.g., missing transforms, plugin load failure).

---

## Chunk 2: Likely Fix — Nav2 Params & Launch Configuration

Based on common failure patterns with this exact setup (SLAM Toolbox localization + Nav2 navigation_launch.py), these are the most likely required fixes.

### Task 4: Verify `navigation_launch.py` arguments are correct

The orchestrator starts Nav2 with:
```python
extra_args = [f"params_file:={NAV2_PARAMS_FILE}"]
# NAV2_PARAMS_FILE = /ros2_ws/install/slam/share/slam/config/nav2_params.yaml

if state.active_map:
    extra_args.append(f"map:={map_yaml}")
```

The standard `nav2_bringup/navigation_launch.py` accepts these arguments:
- `params_file` — the nav2 params YAML
- `map` — path to map YAML (only used if it launches map_server internally)
- `use_sim_time`
- `autostart` — defaults to true

**Files:**
- Modify: `orchestrator/robot_orchestrator.py:741-749` (autonomy start)
- Modify: `slam/config/nav2_params.yaml:258-269` (lifecycle_manager)

- [ ] **Step 1: Check if `navigation_launch.py` passes `params_file` correctly**

The nav2_bringup `navigation_launch.py` in Humble remaps the params file to each node. Verify the params_file path exists inside the lidar_node container:

```bash
# Inside lidar_node container
ls -la /ros2_ws/install/slam/share/slam/config/nav2_params.yaml
```

If the file doesn't exist, the nodes get default params and the lifecycle_manager's `node_names` won't match.

- [ ] **Step 2: Clean up the `map` argument and add useful launch args**

The `navigation_launch.py` in nav2_bringup (Humble) declares a `map` argument but doesn't use it to launch a map_server — that's `bringup_launch.py`'s job. However, passing an unused argument creates confusion and could break if the launch file changes. Since SLAM Toolbox publishes `/map` directly, remove it.

In `orchestrator/robot_orchestrator.py`, modify the `/autonomy/start` endpoint:

```python
# Lines 741-749 — clean up launch args
@app.post("/autonomy/start", tags=["Autonomy"])
def start_autonomy():
    require_mode(
        RobotMode.LOCALIZING, RobotMode.IDLE,
        detail="Start localization first before enabling autonomy",
    )
    if not ros_node.launch_running("localization"):
        raise HTTPException(
            409, "Localization stack is not running. Call /localization/start first.")

    extra_args = [
        f"params_file:={NAV2_PARAMS_FILE}",
        "use_respawn:=true",        # restart crashed nodes automatically
        "autostart:=true",          # lifecycle_manager auto-transitions nodes
    ]
    # NOTE: Do NOT pass map:= argument — /map topic is provided by SLAM Toolbox
    # localization. navigation_launch.py doesn't use it, but passing it is
    # misleading and could break with future Nav2 versions.

    ros_node.launch_start("nav2", NAV2_LAUNCH_PKG,
                          NAV2_LAUNCH_FILE, extra_args=extra_args)
    state.mode = RobotMode.AUTONOMOUS
    return {"status": "autonomy stack started", "map": state.active_map}
```

- [ ] **Step 3: Commit diagnostic fix**

```bash
git add orchestrator/robot_orchestrator.py
git commit -m "fix: remove map arg from nav2 launch to avoid map_server conflict with SLAM Toolbox"
```

### Task 5: Trim lifecycle_manager node list to essential nodes

**This is the most likely root cause fix.** The `nav2_params.yaml` lifecycle_manager lists 6 nodes, but we only need 4 for basic navigation. If `smoother_server` or `waypoint_follower` crash (or take too long to start), the lifecycle_manager stalls and never activates the critical nodes like `bt_navigator`.

**Files:**
- Modify: `slam/config/nav2_params.yaml:258-269`

- [ ] **Step 1: Trim the lifecycle_manager node_names to only essential navigation nodes**

```yaml
lifecycle_manager:
  ros__parameters:
    use_sim_time: false
    autostart: true
    node_names:
      - controller_server
      - planner_server
      - behavior_server
      - bt_navigator
```

Remove `smoother_server` and `waypoint_follower` — they can be added back once basic navigation works.

- [ ] **Step 2: Commit**

```bash
git add slam/config/nav2_params.yaml
git commit -m "fix: trim Nav2 lifecycle_manager to essential nodes to prevent chain stall"
```

### Task 6: Add Nav2 startup wait with retry to orchestrator

The NavigateToPose action server becomes available only after `bt_navigator` reaches the **active** lifecycle state. The lifecycle_manager transition takes 10-30 seconds. Currently the orchestrator returns "autonomy started" immediately, but the action server isn't ready yet.

**Files:**
- Modify: `orchestrator/robot_orchestrator.py:384-412` (send_goal method)
- Modify: `orchestrator/robot_orchestrator.py:727-751` (start_autonomy endpoint)

- [ ] **Step 1: Add a lifecycle readiness wait to start_autonomy**

After launching nav2, poll the lifecycle nodes until they reach "active" or a timeout elapses. This gives the user a clear signal that autonomy is actually ready.

Add this method to `OrchestratorNode`:

```python
def wait_for_nav2_ready(self, timeout: float = 30.0) -> bool:
    """Poll Nav2 lifecycle nodes until all are active or timeout."""
    end = time.time() + timeout
    target_nodes = ["controller_server", "bt_navigator", "planner_server", "behavior_server"]
    while time.time() < end:
        states = self.get_nav2_lifecycle()
        active_count = sum(1 for s in states.values() if s == "active")
        log.info(f"Nav2 lifecycle check: {states}")
        if active_count >= len(target_nodes):
            return True
        time.sleep(2.0)
    return False
```

- [ ] **Step 2: Call the wait in start_autonomy**

After `ros_node.launch_start("nav2", ...)`, add:

```python
    log.info("Waiting for Nav2 lifecycle nodes to become active...")
    if not ros_node.wait_for_nav2_ready(timeout=30.0):
        lifecycle = ros_node.get_nav2_lifecycle()
        log.warning(f"Nav2 lifecycle not fully active after 30s: {lifecycle}")
        return {
            "status": "autonomy started (nav2 still initializing)",
            "map": state.active_map,
            "nav2_lifecycle": lifecycle,
            "warning": "Nav2 nodes not fully active yet. Check /status for updates.",
        }
```

> **Note:** This blocks the HTTP request for up to 30s. Ensure your HTTP client timeout is >30s. Alternatively, return immediately and let the client poll `/status`.

- [ ] **Step 3: Commit**

```bash
git add orchestrator/robot_orchestrator.py
git commit -m "feat: add Nav2 lifecycle readiness wait in start_autonomy"
```

### Task 7: Improve send_goal to wait for action server with better error messages

**Files:**
- Modify: `orchestrator/robot_orchestrator.py:384-412`

- [ ] **Step 1: Increase action server wait timeout and add lifecycle context to errors**

Replace the `send_goal` method's server wait:

```python
def send_goal(self, x: float, y: float, yaw: float = 0.0, frame: str = FIXED_FRAME):
    """Send a NavigateToPose goal. Returns the goal handle."""
    import math
    from geometry_msgs.msg import Quaternion

    if not self._nav_action_client.wait_for_server(timeout_sec=10.0):
        # Provide lifecycle context in the error
        lifecycle = self.get_nav2_lifecycle()
        raise RuntimeError(
            f"NavigateToPose action server not available. "
            f"Nav2 lifecycle states: {lifecycle}. "
            f"bt_navigator must be 'active' to accept goals."
        )

    goal_msg = NavigateToPose.Goal()
    goal_msg.pose = PoseStamped()
    goal_msg.pose.header.frame_id = frame
    goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
    goal_msg.pose.pose.position.x = x
    goal_msg.pose.pose.position.y = y
    goal_msg.pose.pose.position.z = 0.0

    half_yaw = yaw / 2.0
    goal_msg.pose.pose.orientation = Quaternion(
        x=0.0, y=0.0,
        z=math.sin(half_yaw),
        w=math.cos(half_yaw),
    )

    future = self._nav_action_client.send_goal_async(goal_msg)
    goal_handle = self._wait_for_future(future, timeout=10.0)
    if not goal_handle or not goal_handle.accepted:
        raise RuntimeError("Navigation goal was rejected by Nav2")
    return goal_handle
```

- [ ] **Step 2: Commit**

```bash
git add orchestrator/robot_orchestrator.py
git commit -m "fix: improve NavigateToPose error with lifecycle state context"
```

---

## Chunk 3: Fixes based on diagnostic findings

These tasks address specific failure modes discovered in Chunk 1. **Execute only the tasks that match your diagnostic findings.**

### Task 8: (If `/map` topic is missing) — Fix SLAM Toolbox localization map publishing

SLAM Toolbox in localization mode should publish on `/map`. If it's not, the issue is likely with the `map_file` argument or the localization params.

**Files:**
- Check: `slam/config/mapper_params_localization.yaml`

- [ ] **Step 1: Verify SLAM Toolbox localization is publishing /map**

Inside the lidar_node container while localization is running:

```bash
ros2 topic info /map
```

Expected: at least one publisher (from `slam_toolbox`). If zero publishers, the SLAM Toolbox localization node isn't running or failed to load the map.

- [ ] **Step 2: Check SLAM Toolbox logs for map load errors**

```bash
docker compose logs lidar_node 2>&1 | grep -i "slam_toolbox\|map\|error"
```

Common issue: the `map_file` path passed via `map_file:=/ros2_ws/maps/my_map_name` needs to be a path WITHOUT the `.yaml` extension for SLAM Toolbox (it appends `.posegraph` / `.data` itself), while `map_server` needs the `.yaml` extension. Verify the localization launch file uses the correct form.

Looking at `slam_localization.launch.py:50`, the param is `map_file_name: map_file` — and the orchestrator passes `map_file:=/ros2_ws/maps/my_map_name` (no extension), which is correct for SLAM Toolbox's `map_file_name` parameter.

### Task 9: (If TF `map→odom` is missing) — Debug transform chain

- [ ] **Step 1: Verify kobuki publishes `odom→base_footprint`**

```bash
ros2 run tf2_ros tf2_echo odom base_footprint
```

- [ ] **Step 2: Verify SLAM Toolbox publishes `map→odom`**

```bash
ros2 run tf2_ros tf2_echo map odom
```

If `map→odom` is missing, SLAM Toolbox localization either isn't running or failed to localize. Check if `set_initial_pose` was called — SLAM Toolbox in localization mode may need this to start publishing the transform.

### Task 10: (If lifecycle_manager reports bond failures) — Further lifecycle debugging

> **Note:** Task 5 already trimmed the lifecycle_manager to 4 essential nodes. If the problem persists after that fix, investigate further here.

- [ ] **Step 1: Check which nodes actually exist after nav2 launch**

```bash
ros2 lifecycle nodes
```

Compare against the trimmed `node_names` (controller_server, planner_server, behavior_server, bt_navigator). If a node is listed but doesn't exist (crashed), the lifecycle_manager blocks.

- [ ] **Step 2: If a node is crashing, check its individual logs and try manual configuration**

The most common crash causes:
- **controller_server**: missing transforms or `/scan` topic
- **planner_server**: missing `/map` topic (global costmap can't initialize)
- **bt_navigator**: can't load BT XML file
- **behavior_server**: missing transforms

```bash
# Try configuring manually to see the exact error
ros2 lifecycle set /controller_server configure
ros2 lifecycle set /planner_server configure
```

---

## Chunk 4: End-to-end validation

### Task 11: Full integration test sequence

Run this complete sequence on the robot after applying fixes:

- [ ] **Step 1: Rebuild affected containers**

```bash
docker compose build lidar_node orchestrator
docker compose up -d
```

- [ ] **Step 2: Start localization**

```bash
curl -X POST http://<robot-ip>:8080/localization/start \
  -H "Content-Type: application/json" \
  -d '{"name": "my_map_name"}'
```

Verify response shows success.

- [ ] **Step 3: Set initial pose**

```bash
curl -X POST http://<robot-ip>:8080/localization/set_initial_pose \
  -H "Content-Type: application/json" \
  -d '{"x": 0.0, "y": 0.0, "yaw": 0.0}'
```

- [ ] **Step 4: Verify TF and /map are working**

```bash
# Inside lidar_node container
ros2 run tf2_ros tf2_echo map base_footprint  # Should show transforms
ros2 topic echo /map --once                    # Should return map data
```

- [ ] **Step 5: Start autonomy**

```bash
curl -X POST http://<robot-ip>:8080/autonomy/start
```

Expected: response includes lifecycle states. Wait for "autonomy started" (may take up to 60s with the new wait).

- [ ] **Step 6: Check /status — all lifecycle nodes should be "active"**

```bash
curl http://<robot-ip>:8080/status | python3 -m json.tool
```

Expected:
```json
"nav2_lifecycle": {
    "controller_server": "active",
    "planner_server": "active",
    "bt_navigator": "active",
    "behavior_server": "active"
}
```

- [ ] **Step 7: Send a navigation goal**

```bash
curl -X POST http://<robot-ip>:8080/navigation/goto \
  -H "Content-Type: application/json" \
  -d '{"x": 1.0, "y": 0.0, "yaw": 0.0}'
```

Expected: `{"status": "goal accepted", "target": ...}`

- [ ] **Step 8: Monitor navigation progress**

```bash
curl http://<robot-ip>:8080/navigation/status
```

Expected: `{"goal_active": true, "status": "executing"}`

- [ ] **Step 9: Commit all remaining changes**

```bash
git add orchestrator/robot_orchestrator.py slam/config/nav2_params.yaml
git commit -m "feat: Nav2 integration working end-to-end"
```

---

## Quick Reference: Debug Commands Cheat Sheet

| What to check | Command (inside lidar_node container) |
|---|---|
| Nav2 logs | `docker compose logs lidar_node --tail=200` |
| TF tree | `ros2 run tf2_ros tf2_echo map base_footprint` |
| /map topic | `ros2 topic echo /map --once` |
| Lifecycle nodes | `ros2 lifecycle nodes` |
| Node state | `ros2 lifecycle get /<node_name>` |
| Manual configure | `ros2 lifecycle set /<node_name> configure` |
| Active topics | `ros2 topic list` |
| Action servers | `ros2 action list` |
| /map QoS check | `ros2 topic info /map --verbose` |
| Nav2 costmap | `ros2 topic echo /global_costmap/costmap --once` |

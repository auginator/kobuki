"""
Kobuki Robot Orchestrator
=========================
A FastAPI server that manages the lifecycle of ROS2 nodes and launch files
for the Kobuki robot platform. Exposes an HTTP API for:
  - SLAM mapping (start, stop, save)
  - Localization in a saved map
  - Map annotation loading
  - Nav2 autonomy stack management
  - Goal sending
  - Dock return

Launch files are executed remotely via the launch_agent node running in the
lidar_node container. The orchestrator communicates with it over ROS2 services
(transported via Zenoh across the Docker network).

Run this inside your Docker network where ROS_DOMAIN_ID is shared with other containers.
"""

import json
import logging
import os
import subprocess
import time
from contextlib import asynccontextmanager
from enum import Enum
from pathlib import Path
from typing import Optional

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from launch_agent_interfaces.srv import LaunchStart, LaunchStop, LaunchStatus
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node
from std_srvs.srv import Empty

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ROS_WS = Path(os.environ.get("ROS_WS", "/ros2_ws"))
MAPS_DIR = ROS_WS / "maps"
MAPS_DIR.mkdir(parents=True, exist_ok=True)

MAPPING_LAUNCH_PKG = os.environ.get("MAPPING_LAUNCH_PKG", "slam")
MAPPING_LAUNCH_FILE = os.environ.get(
    "MAPPING_LAUNCH_FILE", "slam_mapping.launch.py")
LOCALIZATION_LAUNCH_PKG = os.environ.get("LOCALIZATION_LAUNCH_PKG", "slam")
LOCALIZATION_LAUNCH_FILE = os.environ.get(
    "LOCALIZATION_LAUNCH_FILE", "slam_localization.launch.py")
NAV2_LAUNCH_PKG = os.environ.get("NAV2_LAUNCH_PKG", "nav2_bringup")
NAV2_LAUNCH_FILE = os.environ.get("NAV2_LAUNCH_FILE", "navigation_launch.py")
NAV2_PARAMS_FILE = os.environ.get(
    "NAV2_PARAMS_FILE", "/ros2_ws/install/slam/share/slam/config/nav2_params.yaml")
JOYSTICK_LAUNCH_PKG = os.environ.get("JOYSTICK_LAUNCH_PKG", "slam")
JOYSTICK_LAUNCH_FILE = os.environ.get(
    "JOYSTICK_LAUNCH_FILE", "joy_teleop.launch.py")

# All known launch keys — used by kill_all / e-stop
ALL_LAUNCH_KEYS = ["mapping", "localization", "nav2", "joystick"]

FIXED_FRAME = "map"
BASE_FRAME = "base_footprint"

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("orchestrator")


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


# ---------------------------------------------------------------------------
# Robot state
# ---------------------------------------------------------------------------

class RobotMode(str, Enum):
    IDLE = "idle"
    MAPPING = "mapping"
    LOCALIZING = "localizing"
    AUTONOMOUS = "autonomous"
    RETURNING_TO_DOCK = "returning_to_dock"


class RobotState:
    """Single source of truth for what the robot is currently doing."""

    def __init__(self):
        self.mode: RobotMode = RobotMode.IDLE
        self.active_map: Optional[str] = None
        self.active_annotations: Optional[str] = None
        self.annotations: dict = {}
        self.current_goal_handle = None

    def to_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "active_map": self.active_map,
            "active_annotations": self.active_annotations,
            "annotation_count": len(self.annotations.get("waypoints", [])),
        }


# ---------------------------------------------------------------------------
# ROS2 node (runs in a background thread via rclpy.spin)
# ---------------------------------------------------------------------------

class OrchestratorNode(Node):
    """
    Thin ROS2 node used to call services and send actions.
    Launch file management is delegated to the launch_agent in lidar_node.
    """

    def __init__(self):
        super().__init__("robot_orchestrator")
        self._nav_action_client = ActionClient(
            self, NavigateToPose, "navigate_to_pose")
        self._clear_costmap_client = self.create_client(
            Empty, "/global_costmap/clear_entirely_global_costmap")

        # Launch agent service clients
        self._launch_start_client = self.create_client(
            LaunchStart, "launch_agent/start")
        self._launch_stop_client = self.create_client(
            LaunchStop, "launch_agent/stop")
        self._launch_status_client = self.create_client(
            LaunchStatus, "launch_agent/status")

        self.get_logger().info("OrchestratorNode ready")

    # ------------------------------------------------------------------
    # Service helpers
    # ------------------------------------------------------------------

    def _call_service(self, client, request, timeout=5.0):
        if not client.wait_for_service(timeout_sec=timeout):
            raise RuntimeError(f"Service {client.srv_name} not available")
        future = client.call_async(request)
        rclpy.spin_until_future_complete(self, future, timeout_sec=timeout)
        if future.result() is None:
            raise RuntimeError(f"Service call to {client.srv_name} failed")
        return future.result()

    # ------------------------------------------------------------------
    # Launch agent helpers
    # ------------------------------------------------------------------

    def launch_start(self, key: str, pkg: str, launch_file: str, extra_args: list[str] = None):
        """Start a launch file on the remote launch agent."""
        req = LaunchStart.Request()
        req.key = key
        req.launch_package = pkg
        req.launch_file = launch_file
        req.extra_args = extra_args or []
        log.info("Requesting launch agent start: [%s] %s/%s %s",
                 key, pkg, launch_file, req.extra_args)
        result = self._call_service(self._launch_start_client, req, timeout=10.0)
        if not result.success:
            raise RuntimeError(f"Launch agent start failed: {result.message}")
        log.info("Launch agent started [%s]: %s", key, result.message)
        return result

    def launch_stop(self, key: str):
        """Stop a launch file on the remote launch agent. No-op if agent unreachable."""
        req = LaunchStop.Request()
        req.key = key
        log.info("Requesting launch agent stop: [%s]", key)
        try:
            result = self._call_service(self._launch_stop_client, req, timeout=15.0)
        except RuntimeError as e:
            log.warning("Launch agent unreachable for stop [%s]: %s", key, e)
            return None
        if not result.success:
            raise RuntimeError(f"Launch agent stop failed: {result.message}")
        log.info("Launch agent stopped [%s]: %s", key, result.message)
        return result

    def launch_running(self, key: str) -> bool:
        """Check if a launch key is running. Returns False if agent unreachable."""
        req = LaunchStatus.Request()
        req.key = key
        try:
            result = self._call_service(self._launch_status_client, req, timeout=5.0)
        except RuntimeError:
            log.warning("Launch agent unreachable for status check [%s]", key)
            return False
        for i, k in enumerate(result.keys):
            if k == key:
                return result.running[i]
        return False

    def launch_stop_all(self):
        """Stop all known launch keys. Best-effort — errors are logged but not raised."""
        for key in ALL_LAUNCH_KEYS:
            try:
                self.launch_stop(key)
            except Exception as e:
                log.warning("Failed to stop [%s] during kill_all: %s", key, e)

    # ------------------------------------------------------------------
    # Map saving
    # ------------------------------------------------------------------

    def save_map(self, map_stem: str):
        """
        Call the slam_toolbox save_map service. This is done via subprocess
        because the srv type import is optional depending on install.
        """
        map_path = str(MAPS_DIR / map_stem)
        result = subprocess.run(
            [
                "ros2", "service", "call",
                "/slam_toolbox/save_map",
                "slam_toolbox/srv/SaveMap",
                f"{{name: {{data: '{map_path}'}}}}",
            ],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Map save failed: {result.stderr}")
        log.info("Map saved to %s", map_path)

    def clear_costmaps(self):
        req = Empty.Request()
        self._call_service(self._clear_costmap_client, req)

    # ------------------------------------------------------------------
    # Navigation actions
    # ------------------------------------------------------------------

    def send_goal(self, x: float, y: float, yaw: float = 0.0, frame: str = FIXED_FRAME):
        """Send a NavigateToPose goal. Returns the goal handle."""
        import math
        from geometry_msgs.msg import Quaternion

        if not self._nav_action_client.wait_for_server(timeout_sec=5.0):
            raise RuntimeError("NavigateToPose action server not available")

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = PoseStamped()
        goal_msg.pose.header.frame_id = frame
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose.position.x = x
        goal_msg.pose.pose.position.y = y
        goal_msg.pose.pose.position.z = 0.0

        # Convert yaw to quaternion
        half_yaw = yaw / 2.0
        goal_msg.pose.pose.orientation = Quaternion(
            x=0.0, y=0.0,
            z=math.sin(half_yaw),
            w=math.cos(half_yaw),
        )

        future = self._nav_action_client.send_goal_async(goal_msg)
        rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)
        goal_handle = future.result()
        if not goal_handle or not goal_handle.accepted:
            raise RuntimeError("Navigation goal was rejected by Nav2")
        return goal_handle

    def cancel_current_goal(self, goal_handle):
        if goal_handle is None:
            return
        future = goal_handle.cancel_goal_async()
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)


# ---------------------------------------------------------------------------
# Global singletons — initialised in lifespan
# ---------------------------------------------------------------------------

state = RobotState()
ros_node: Optional[OrchestratorNode] = None
_ros_thread = None


def _spin_ros():
    """Run rclpy.spin in a dedicated thread so it doesn't block FastAPI."""
    rclpy.spin(ros_node)


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
    try:
        ros_node.launch_stop_all()
    except Exception as e:
        log.warning("Error stopping launches on shutdown: %s", e)
    rclpy.shutdown()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Kobuki Robot Orchestrator",
    description="HTTP API for managing Kobuki robot modes, mapping, and navigation.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten this if you expose beyond LAN
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class MapName(BaseModel):
    name: str = Field(...,
                      description="Map stem name, e.g. 'living_room'. No extension, no path.")


class GoalRequest(BaseModel):
    x: float = Field(..., description="Goal X in map frame (metres)")
    y: float = Field(..., description="Goal Y in map frame (metres)")
    yaw: float = Field(
        0.0, description="Goal heading in radians (0 = east / +X direction)")


class InitialPose(BaseModel):
    x: float
    y: float
    yaw: float = 0.0
    covariance: float = Field(
        0.5, description="Diagonal covariance value for the pose estimate")


# ---------------------------------------------------------------------------
# Utility: require a specific mode (or list of modes) to be active
# ---------------------------------------------------------------------------

def require_mode(*modes: RobotMode, detail: str = None):
    if state.mode not in modes:
        raise HTTPException(
            status_code=409,
            detail=detail or f"Robot must be in one of {[m.value for m in modes]} (currently '{state.mode.value}')",
        )


# ---------------------------------------------------------------------------
# Routes — Status
# ---------------------------------------------------------------------------

@app.get("/status", tags=["Status"])
def get_status():
    """Return full robot state snapshot."""
    return state.to_dict()


@app.get("/maps", tags=["Status"])
def list_maps():
    """Return available saved maps and annotation files."""
    maps = [p.stem for p in MAPS_DIR.glob("*.yaml")]
    annotations = [p.name for p in MAPS_DIR.glob("*.annotations.json")]
    return {"maps": sorted(maps), "annotations": sorted(annotations)}


# ---------------------------------------------------------------------------
# Routes — Mapping
# ---------------------------------------------------------------------------

@app.post("/mapping/start", tags=["Mapping"])
def start_mapping():
    """
    Launch the SLAM toolbox in mapping mode.
    Transitions robot into MAPPING state.
    Any previously running mapping or localization session is stopped first.
    """
    if state.mode == RobotMode.MAPPING:
        raise HTTPException(409, "Already in mapping mode")

    # Stop conflicting stacks
    ros_node.launch_stop("localization")
    ros_node.launch_stop("nav2")
    state.current_goal_handle = None

    ros_node.launch_start("mapping", MAPPING_LAUNCH_PKG, MAPPING_LAUNCH_FILE)
    state.mode = RobotMode.MAPPING
    state.active_map = None
    return {"status": "mapping started"}


@app.post("/mapping/stop", tags=["Mapping"])
def stop_mapping(body: MapName):
    """
    Save the current map then stop the SLAM toolbox.
    Map is saved as maps/<name>.yaml (and .pgm).
    """
    require_mode(RobotMode.MAPPING,
                 detail="Must be in mapping mode to save and stop")

    try:
        ros_node.save_map(body.name)
    except Exception as e:
        raise HTTPException(500, f"Failed to save map: {e}")

    ros_node.launch_stop("mapping")
    state.mode = RobotMode.IDLE
    state.active_map = body.name
    return {"status": "map saved", "map": body.name}


@app.post("/mapping/save", tags=["Mapping"])
def save_map_only(body: MapName):
    """
    Save the map without stopping — useful for checkpointing during a long mapping run.
    """
    require_mode(RobotMode.MAPPING)
    try:
        ros_node.save_map(body.name)
    except Exception as e:
        raise HTTPException(500, f"Failed to save map: {e}")
    state.active_map = body.name
    return {"status": "map saved (mapping still active)", "map": body.name}


# ---------------------------------------------------------------------------
# Routes — Localization
# ---------------------------------------------------------------------------

@app.post("/localization/start", tags=["Localization"])
def start_localization(body: MapName):
    """
    Load a saved map and start SLAM toolbox in localization mode.
    """
    map_yaml = MAPS_DIR / f"{body.name}.yaml"
    if not map_yaml.exists():
        raise HTTPException(404, f"Map '{body.name}' not found at {map_yaml}")

    # Stop conflicting stacks
    ros_node.launch_stop("mapping")
    ros_node.launch_stop("nav2")

    ros_node.launch_start(
        "localization",
        LOCALIZATION_LAUNCH_PKG,
        LOCALIZATION_LAUNCH_FILE,
        extra_args=[f"map_file:={MAPS_DIR / body.name}"],
    )
    state.mode = RobotMode.LOCALIZING
    state.active_map = body.name
    return {"status": "localization started", "map": body.name}


@app.post("/localization/set_initial_pose", tags=["Localization"])
def set_initial_pose(body: InitialPose):
    """
    Publish an initial pose estimate to help AMCL / SLAM toolbox converge.
    Call this after starting localization if the robot doesn't know where it is.
    """
    import math
    require_mode(RobotMode.LOCALIZING, RobotMode.AUTONOMOUS)

    msg = PoseWithCovarianceStamped()
    msg.header.frame_id = FIXED_FRAME
    msg.header.stamp = ros_node.get_clock().now().to_msg()
    msg.pose.pose.position.x = body.x
    msg.pose.pose.position.y = body.y
    half_yaw = body.yaw / 2.0
    msg.pose.pose.orientation.z = math.sin(half_yaw)
    msg.pose.pose.orientation.w = math.cos(half_yaw)
    cov = body.covariance
    # 6x6 covariance, only x/y/yaw diagonal entries matter
    c = [0.0] * 36
    c[0] = cov   # x
    c[7] = cov   # y
    c[35] = cov   # yaw
    msg.pose.covariance = c

    pub = ros_node.create_publisher(
        PoseWithCovarianceStamped, "/initialpose", 10)
    pub.publish(msg)
    # Give it a moment then destroy — we don't need the publisher long-term
    time.sleep(0.5)
    ros_node.destroy_publisher(pub)

    return {"status": "initial pose published", "x": body.x, "y": body.y, "yaw": body.yaw}


# ---------------------------------------------------------------------------
# Routes — Annotations
# ---------------------------------------------------------------------------

ANNOTATION_SCHEMA = """
Expected annotation file format (JSON):
{
  "map": "my_map_name",
  "waypoints": [
    { "name": "kitchen",  "x": 1.2, "y": 0.5, "yaw": 0.0 },
    { "name": "dock",     "x": 0.0, "y": 0.0, "yaw": 3.14 }
  ],
  "dock": { "x": 0.0, "y": 0.0, "yaw": 3.14 }
}
"""


@app.post("/annotations/load", tags=["Annotations"])
def load_annotations(body: MapName):
    """
    Load a <name>.annotations.json file from the maps directory.
    Annotations include named waypoints and the dock position.
    """
    ann_path = MAPS_DIR / f"{body.name}.annotations.json"
    if not ann_path.exists():
        raise HTTPException(
            404,
            f"Annotation file not found: {ann_path}\n{ANNOTATION_SCHEMA}",
        )
    with open(ann_path) as f:
        data = json.load(f)

    state.annotations = data
    state.active_annotations = str(ann_path)
    return {
        "status": "annotations loaded",
        "file": str(ann_path),
        "waypoint_count": len(data.get("waypoints", [])),
        "waypoints": [w["name"] for w in data.get("waypoints", [])],
        "has_dock": "dock" in data,
    }


@app.get("/annotations/waypoints", tags=["Annotations"])
def list_waypoints():
    """List loaded named waypoints."""
    if not state.annotations:
        raise HTTPException(
            409, "No annotations loaded. Call /annotations/load first.")
    return {"waypoints": state.annotations.get("waypoints", [])}


@app.post("/annotations/save", tags=["Annotations"])
def save_annotations(body: dict):
    """
    Write an annotation file. POST the full JSON body matching the schema above.
    Useful for saving waypoints defined in the web UI after a mapping session.
    """
    name = body.get("map")
    if not name:
        raise HTTPException(400, "Annotation body must include 'map' field")
    ann_path = MAPS_DIR / f"{name}.annotations.json"
    with open(ann_path, "w") as f:
        json.dump(body, f, indent=2)
    return {"status": "annotations saved", "file": str(ann_path)}


# ---------------------------------------------------------------------------
# Routes — Autonomy (Nav2)
# ---------------------------------------------------------------------------

@app.post("/autonomy/start", tags=["Autonomy"])
def start_autonomy():
    """
    Start the Nav2 navigation stack. Requires localization to already be running.
    Nav2 will use the /map topic and /tf from the localization stack.
    """
    require_mode(
        RobotMode.LOCALIZING, RobotMode.IDLE,
        detail="Start localization first before enabling autonomy",
    )
    if not ros_node.launch_running("localization"):
        raise HTTPException(
            409, "Localization stack is not running. Call /localization/start first.")

    # Build launch args — params file and map are on the lidar_node container
    extra_args = [f"params_file:={NAV2_PARAMS_FILE}"]

    if state.active_map:
        map_yaml = MAPS_DIR / f"{state.active_map}.yaml"
        extra_args.append(f"map:={map_yaml}")

    ros_node.launch_start("nav2", NAV2_LAUNCH_PKG,
                          NAV2_LAUNCH_FILE, extra_args=extra_args)
    state.mode = RobotMode.AUTONOMOUS
    return {"status": "autonomy stack started", "map": state.active_map}


@app.post("/autonomy/stop", tags=["Autonomy"])
def stop_autonomy():
    """Stop the Nav2 stack and cancel any active goals."""
    if state.current_goal_handle:
        try:
            ros_node.cancel_current_goal(state.current_goal_handle)
        except Exception as e:
            log.warning("Error cancelling goal on stop: %s", e)
        state.current_goal_handle = None

    ros_node.launch_stop("nav2")
    # Drop back to localizing if that stack is still alive
    if ros_node.launch_running("localization"):
        state.mode = RobotMode.LOCALIZING
    else:
        state.mode = RobotMode.IDLE
    return {"status": "autonomy stopped"}


# ---------------------------------------------------------------------------
# Routes — Joystick
# ---------------------------------------------------------------------------

@app.post("/joystick/start", tags=["Joystick"])
def start_joystick():
    """
    Start joystick teleoperation as an overlay control process.
    This does not change the robot mode state machine.
    """
    if ros_node.launch_running("joystick"):
        raise HTTPException(409, "Joystick control is already running")

    try:
        ros_node.launch_start("joystick", JOYSTICK_LAUNCH_PKG,
                              JOYSTICK_LAUNCH_FILE)
    except Exception as e:
        raise HTTPException(500, f"Failed to start joystick control: {e}")

    return {
        "status": "joystick control started",
        "launch": f"{JOYSTICK_LAUNCH_PKG}/{JOYSTICK_LAUNCH_FILE}",
        "mode": state.mode.value,
    }


@app.post("/joystick/stop", tags=["Joystick"])
def stop_joystick():
    """
    Stop joystick teleoperation overlay process.
    This endpoint is idempotent and does not change robot mode.
    """
    if not ros_node.launch_running("joystick"):
        return {
            "status": "joystick control already stopped",
            "mode": state.mode.value,
        }

    ros_node.launch_stop("joystick")
    return {
        "status": "joystick control stopped",
        "mode": state.mode.value,
    }


# ---------------------------------------------------------------------------
# Routes — Navigation goals
# ---------------------------------------------------------------------------

@app.post("/navigation/goto", tags=["Navigation"])
def goto(body: GoalRequest):
    """
    Send a NavigateToPose goal to Nav2.
    The call returns immediately; navigation runs asynchronously.
    Check /navigation/status for progress.
    """
    require_mode(RobotMode.AUTONOMOUS,
                 detail="Start the autonomy stack first (/autonomy/start)")

    # Cancel any in-flight goal
    if state.current_goal_handle:
        try:
            ros_node.cancel_current_goal(state.current_goal_handle)
        except Exception:
            pass

    try:
        goal_handle = ros_node.send_goal(body.x, body.y, body.yaw)
    except RuntimeError as e:
        raise HTTPException(500, str(e))

    state.current_goal_handle = goal_handle
    return {
        "status": "goal accepted",
        "target": {"x": body.x, "y": body.y, "yaw": body.yaw},
    }


@app.post("/navigation/goto_waypoint/{name}", tags=["Navigation"])
def goto_waypoint(name: str):
    """
    Navigate to a named waypoint from the loaded annotation file.
    Requires annotations to be loaded first via /annotations/load.
    """
    require_mode(RobotMode.AUTONOMOUS)
    if not state.annotations:
        raise HTTPException(409, "No annotations loaded")

    waypoints = {w["name"]: w for w in state.annotations.get("waypoints", [])}
    if name not in waypoints:
        raise HTTPException(
            404, f"Waypoint '{name}' not found. Available: {list(waypoints.keys())}")

    wp = waypoints[name]
    try:
        goal_handle = ros_node.send_goal(wp["x"], wp["y"], wp.get("yaw", 0.0))
    except RuntimeError as e:
        raise HTTPException(500, str(e))

    state.current_goal_handle = goal_handle
    return {"status": "goal accepted", "waypoint": name, "target": wp}


@app.post("/navigation/cancel", tags=["Navigation"])
def cancel_navigation():
    """Cancel the currently active navigation goal."""
    if not state.current_goal_handle:
        return {"status": "no active goal"}
    try:
        ros_node.cancel_current_goal(state.current_goal_handle)
    except Exception as e:
        raise HTTPException(500, f"Failed to cancel goal: {e}")
    state.current_goal_handle = None
    return {"status": "goal cancelled"}


@app.get("/navigation/status", tags=["Navigation"])
def navigation_status():
    """Return the status of the current navigation goal."""
    if not state.current_goal_handle:
        return {"goal_active": False, "status": "idle"}

    status_map = {
        GoalStatus.STATUS_UNKNOWN:   "unknown",
        GoalStatus.STATUS_ACCEPTED:  "accepted",
        GoalStatus.STATUS_EXECUTING: "executing",
        GoalStatus.STATUS_CANCELING: "canceling",
        GoalStatus.STATUS_SUCCEEDED: "succeeded",
        GoalStatus.STATUS_CANCELED:  "canceled",
        GoalStatus.STATUS_ABORTED:   "aborted",
    }
    code = state.current_goal_handle.status
    return {
        "goal_active": code in (GoalStatus.STATUS_ACCEPTED, GoalStatus.STATUS_EXECUTING),
        "status": status_map.get(code, "unknown"),
        "code": code,
    }


# ---------------------------------------------------------------------------
# Routes — Dock return
# ---------------------------------------------------------------------------

@app.post("/dock/return", tags=["Dock"])
def return_to_dock():
    """
    Navigate to the dock position defined in the loaded annotations,
    then trigger the Kobuki auto-docking sequence.

    Two-phase approach:
      1. Nav2 navigates to the rough dock pose (from annotations)
      2. A ROS2 service call triggers Kobuki's IR-guided auto-dock

    If no annotation dock pose is defined, phase 1 is skipped and
    we attempt auto-dock from wherever the robot currently is.
    """
    require_mode(RobotMode.AUTONOMOUS,
                 detail="Autonomy stack must be running to return to dock")

    dock_pose = state.annotations.get("dock") if state.annotations else None

    if dock_pose:
        # Phase 1: Nav2 goal to get close to the dock
        log.info("Navigating toward dock at (%.2f, %.2f)",
                 dock_pose["x"], dock_pose["y"])
        try:
            goal_handle = ros_node.send_goal(
                dock_pose["x"], dock_pose["y"], dock_pose.get("yaw", 0.0)
            )
            state.current_goal_handle = goal_handle
            state.mode = RobotMode.RETURNING_TO_DOCK
        except RuntimeError as e:
            raise HTTPException(500, f"Navigation to dock failed: {e}")

        return {
            "status": "navigating to dock",
            "dock_pose": dock_pose,
            "note": (
                "Robot is navigating to the dock position. "
                "Call /dock/trigger after arrival to engage auto-docking IR sequence."
            ),
        }
    else:
        # No annotation — attempt auto-dock directly from current position
        return _trigger_autodock()


@app.post("/dock/trigger", tags=["Dock"])
def trigger_autodock():
    """
    Trigger the Kobuki IR auto-docking sequence directly.
    The robot should already be near the dock and facing it.
    Useful after /dock/return has completed navigation phase.
    """
    return _trigger_autodock()


def _trigger_autodock() -> dict:
    """
    Call the kobuki_ros auto_dock action or service.
    Kobuki's docking is driven by IR sensors and published via kobuki_ros.
    This sends the ROS2 action goal via subprocess to avoid extra action client setup.
    """
    log.info("Triggering Kobuki auto-dock sequence")
    result = subprocess.run(
        [
            "ros2", "action", "send_goal",
            "/auto_dock",
            "kobuki_ros_interfaces/action/AutoDocking",
            "{}",
        ],
        capture_output=True, text=True, timeout=5,
    )
    if result.returncode != 0:
        # Auto-dock action server might not be present — warn but don't fail hard
        log.warning("Auto-dock action call returned non-zero: %s",
                    result.stderr)
        return {
            "status": "warning",
            "detail": (
                "Auto-dock action server may not be available. "
                "Ensure kobuki_node is running with auto_docking enabled. "
                f"stderr: {result.stderr.strip()}"
            ),
        }
    state.mode = RobotMode.RETURNING_TO_DOCK
    return {"status": "auto-dock sequence triggered"}


# ---------------------------------------------------------------------------
# Routes — Costmap / Utilities
# ---------------------------------------------------------------------------

@app.post("/costmap/clear", tags=["Utilities"])
def clear_costmap():
    """Clear Nav2 global costmap — useful after the environment changes."""
    require_mode(RobotMode.AUTONOMOUS)
    try:
        ros_node.clear_costmaps()
    except Exception as e:
        raise HTTPException(500, f"Failed to clear costmap: {e}")
    return {"status": "costmap cleared"}


@app.post("/estop", tags=["Utilities"])
def emergency_stop():
    """
    Kill all running stacks and cancel navigation immediately.
    Puts robot in IDLE mode.
    """
    log.warning("E-STOP triggered via API")
    if state.current_goal_handle:
        try:
            ros_node.cancel_current_goal(state.current_goal_handle)
        except Exception:
            pass
    state.current_goal_handle = None
    ros_node.launch_stop_all()
    state.mode = RobotMode.IDLE
    return {"status": "emergency stop executed", "mode": "idle"}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "robot_orchestrator:app",
        host="0.0.0.0",
        port=8080,
        reload=False,       # Don't use reload=True with rclpy — it forks the process
        log_level="info",
    )

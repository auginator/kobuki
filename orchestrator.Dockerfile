FROM ros:humble-ros-base

WORKDIR /ros2_ws

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
  python3-pip \
  ros-humble-nav2-msgs \
  ros-humble-nav2-bringup \
  ros-humble-nav2-core \
  ros-humble-nav2-costmap-2d \
  ros-humble-nav2-controller \
  ros-humble-nav2-planner \
  ros-humble-nav2-behaviors \
  ros-humble-nav2-bt-navigator \
  ros-humble-nav2-waypoint-follower \
  ros-humble-nav2-velocity-smoother \
  ros-humble-nav2-lifecycle-manager \
  ros-humble-nav2-regulated-pure-pursuit-controller \
  ros-humble-nav2-navfn-planner \
  ros-humble-nav2-map-server \
  ros-humble-slam-toolbox \
  ros-humble-kobuki-ros-interfaces \
  ros-humble-rmw-zenoh-cpp \
  ros-humble-geometry-msgs \
  ros-humble-action-msgs \
  && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir fastapi uvicorn[standard] pydantic

# Your custom packages (slam, bringup, etc.) should be built and
# installed into this workspace by your CI / compose build step.
# The COPY below assumes you bind-mount or COPY a pre-built install/:
# COPY install/ install/

COPY orchestrator/robot_orchestrator.py /robot_orchestrator.py

# Source ROS + workspace, then run the server
CMD ["/bin/bash", "-c", \
  "source /opt/ros/humble/setup.bash && \
  source /ros2_ws/install/setup.bash 2>/dev/null || true && \
  python3 /robot_orchestrator.py"]

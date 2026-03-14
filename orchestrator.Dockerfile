FROM ros:humble-ros-base

WORKDIR /ros2_ws

# System deps — only what the orchestrator needs for rclpy service calls
RUN apt-get update && apt-get install -y --no-install-recommends \
  python3-pip \
  ros-humble-nav2-msgs \
  ros-humble-kobuki-ros-interfaces \
  ros-humble-rmw-zenoh-cpp \
  ros-humble-geometry-msgs \
  ros-humble-action-msgs \
  ros-humble-slam-toolbox \
  ros-humble-rosidl-default-generators \
  && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir fastapi uvicorn[standard] pydantic

# Build launch_agent_interfaces so we can import the service types
RUN mkdir -p src
COPY launch_agent_interfaces src/launch_agent_interfaces
RUN /bin/bash -c "source /opt/ros/humble/setup.bash && \
  colcon build --packages-select launch_agent_interfaces"

COPY orchestrator/robot_orchestrator.py /robot_orchestrator.py

# Source ROS + workspace, then run the server
CMD ["/bin/bash", "-c", \
  "source /opt/ros/humble/setup.bash && \
  source /ros2_ws/install/setup.bash && \
  python3 /robot_orchestrator.py"]

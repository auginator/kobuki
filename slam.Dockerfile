# lidar.Dockerfile

# Use a ROS2 base image
FROM ros:humble-ros-base

# Set up the workspace directory
WORKDIR /ros2_ws

#  NOTE: NAH, ROS2 base image already has git and python3-rosdep
# Install git and other dependencies -
# RUN apt-get update && apt-get install -y \
#    git \
#    python3-rosdep \
#    && rm -rf /var/lib/apt/lists/*
# Initialize rosdep
#RUN rosdep init && rosdep update

RUN apt-get update && \
  apt-get install -y software-properties-common && \
  add-apt-repository universe && \
  apt-get install -y ros-humble-rmw-cyclonedds-cpp && \
  apt-get install -y ros-humble-xacro && \
  apt-get install -y ros-humble-joint-state-publisher && \
  apt-get install -y ros-humble-robot-state-publisher && \
  apt-get install -y ros-humble-foxglove-bridge && \
  apt-get install -y ros-humble-slam-toolbox && \
  rm -rf /var/lib/apt/lists/*

# Clone the Slamtec Lidar ROS2 driver into the src directory
RUN mkdir -p src && \
  git clone https://github.com/slamtec/sllidar_ros2.git src/sllidar_ros2

# Copy the slam package and kobuki packages into the workspace
COPY slam src/slam
COPY kobuki_ros/kobuki_description src/kobuki_description
COPY kobuki_ros_interfaces src/kobuki_ros_interfaces

# Install dependencies for the cloned package
RUN . /opt/ros/humble/setup.sh && \
  rosdep install -i --from-path src --rosdistro humble -y

# Build the workspace
RUN . /opt/ros/humble/setup.sh && \
  colcon build --symlink-install

# Set the entrypoint to source the workspace and run the node
CMD ["/bin/bash", "-c", ". /opt/ros/humble/setup.sh && . ./install/setup.bash && ros2 launch slam sllidar_with_transform.launch.py"]
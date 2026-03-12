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
  apt-get install -y ros-humble-rmw-zenoh-cpp && \
  rm -rf /var/lib/apt/lists/*

# Clone the Slamtec Lidar ROS2 driver into the src directory
RUN mkdir -p src && \
  git clone https://github.com/slamtec/sllidar_ros2.git src/sllidar_ros2

# Install dependencies for the cloned package
RUN . /opt/ros/humble/setup.sh && \
  rosdep install -i --from-path src --rosdistro humble -y

# Build the workspace
RUN cd src && . /opt/ros/humble/setup.sh  && \
  cd sllidar_ros2 && colcon build --symlink-install

# Set the entrypoint to source the workspace and run the node
CMD ["/bin/bash", "-c", ". /opt/ros/humble/setup.sh && cd src/sllidar_ros2 && . ./install/setup.bash && ros2 launch sllidar_ros2 sllidar_c1_launch.py"]
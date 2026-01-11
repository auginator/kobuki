# bringup.Dockerfile
# Extends the base kobuki image with the augs_bringup package

FROM crl/kobuki:humble as base

# Set up workspace
WORKDIR /kobuki/src

# Copy the augs_bringup package
COPY augs_bringup augs_bringup

# Build the new package
WORKDIR /kobuki
RUN . /opt/ros/humble/setup.sh && \
    . /kobuki/install/setup.sh && \
    colcon build --packages-select augs_bringup --symlink-install

# Clean up
RUN rm -rf /kobuki/log
RUN rm -rf /var/lib/apt/lists/*
RUN apt-get clean

# Set the default command
CMD ["/bin/bash", "-c", ". /opt/ros/humble/setup.sh && . /kobuki/install/setup.bash && ros2 launch augs_bringup augs_kobuki_node.launch.py"]

#!/bin/bash
set -e

# start udev
/lib/systemd/systemd-udevd --daemon

# Wait for udev to process rules and create the kobuki symlink
echo "Waiting for Kobuki device..."
timeout=30
counter=0
while [ ! -e /dev/kobuki ] && [ $counter -lt $timeout ]; do
    sleep 1
    counter=$((counter + 1))
done

if [ -e /dev/kobuki ]; then
    echo "Kobuki device found at /dev/kobuki"
else
    echo "WARNING: Kobuki device not found after ${timeout}s"
fi

# Trigger udev to process any pending events
udevadm trigger
udevadm settle

# setup ros2 environment
source "/opt/ros/$ROS_DISTRO/setup.bash"
source "$WORKSPACE_ROOT/install/setup.bash"


exec "$@"

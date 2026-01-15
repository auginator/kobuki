# Maps Directory

This directory stores SLAM maps created by the slam_toolbox.

## Map Files

Each saved map consists of three files:
- `<map_name>.posegraph` - SLAM toolbox pose graph (used for localization)
- `<map_name>.yaml` - ROS map metadata
- `<map_name>.pgm` - ROS map image (occupancy grid)

## Usage

Maps are created and loaded using the interactive launch files in the slam package.

### Creating a Map
```bash
docker exec -it <container_name> bash
ros2 launch slam slam_mapping.launch.py
# Press 's' to save, 'q' to quit
```

### Loading a Map
```bash
docker exec -it <container_name> bash
ros2 launch slam slam_localization.launch.py
# Select map from interactive list
```

Maps are persisted to the host machine via Docker volume mount.

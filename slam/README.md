# SLAM Package

This package provides SLAM (Simultaneous Localization and Mapping) capabilities for the Kobuki robot using [SLAM Toolbox](https://github.com/SteveMacenski/slam_toolbox) and a SLAMTEC LIDAR.

## Overview

The package includes:
- **LIDAR integration**: Launches the SLAMTEC LIDAR with proper transforms
- **Interactive mapping**: Create maps with user-friendly controls
- **Interactive localization**: Load saved maps for autonomous navigation
- **Foxglove visualization**: Real-time map and robot pose visualization

## Architecture

```
slam/
├── config/                    # SLAM Toolbox configuration files
│   ├── mapper_params_online_async.yaml      # Mapping mode config
│   └── mapper_params_localization.yaml       # Localization mode config
├── launch/                    # ROS2 launch files
│   ├── sllidar_with_transform.launch.py     # Base LIDAR + transforms + Foxglove
│   ├── slam_mapping.launch.py                # Mapping launcher
│   └── slam_localization.launch.py           # Localization launcher
└── scripts/                   # Helper scripts
    ├── slam_controller.py     # Mapping status display
    ├── map_selector.py        # Map selection interface
    └── save_map_helper.py     # Interactive map saving
```

## Prerequisites

- Docker container running with the slam package installed
- SLAMTEC LIDAR connected and available at `/dev/rplidar`
- Foxglove Studio for visualization (optional but recommended)

## Usage

### 1. Start the Base System

The default container runs the LIDAR, transforms, and Foxglove bridge:

```bash
docker compose up -d
```

This starts `sllidar_with_transform.launch.py` which provides:
- LIDAR data on `/s (`base_footprint` → `base_link` → `laser`)
- Foxglove bridge on port 8765

### 2. Create a Map (Mapping Mode)

**Terminal 1 - Start SLAM mapping:**

Execute into the running container and launch the mapping:

```bash
docker exec -it collabs-kobuki-lidar_node-1 bash
ros2 launch slam slam_mapping.launch.py
```

This will:
- Start SLAM Toolbox in mapping mode
- Display instructions and available commands
- Begin building a map as you drive the robot

**Mapping Workflow:**
- Drive the robot around using teleop (in another terminal or via Foxglove)
- View the map being built in real-time in Foxglove (topic: `/map`)
- The mapping will continue until you press `Ctrl+C`

**Terminal 2 - Save the map when ready:**

When you're satisfied with the map coverage, open a second terminal and save it:

```bash
docker exec -it collabs-kobuki-lidar_node-1 bash
ros2 run slam save_map_helper.py
```

You'll be prompted to enter a map name (or accept the auto-generated timestamp name).

**Map Files Created:**
- `<map_name>.posegraph` - SLAM Toolbox pose graph (for localization)
- `<map_name>.yaml` - ROS map metadata
- `<map_name>.pgm` - ROS map occupancy grid image

**Alternative - Save using service calls:**

You can also save maps directly using ROS2 services:

```bash
# Save with custom name
ros2 service call /slam_toolbox/serialize_map slam_toolbox/srv/SerializePoseGraph \
  "{filename: '/ros2_ws/maps/my_map'}"
```
- `<map_name>.pgm` - ROS map occupancy grid image

### 3. Load a Map (Localization Mode)

Execute into the running container and launch the localization interface:

```bash
docker exec -it collabs-kobuki-lidar_node-1 bash
ros2 launch slam slam_localization.launch.py
```

**Interactive Map Selection:**
- The system will display all available maps in the maps directory
- Shows map name, status, and file size
- Enter the map ID number to load
- SLAM Toolbox starts in localization mode

**Alternative: Direct Map Loading**

If you know the map file path, you can load it directly:

```bash
ros2 launch slam slam_localization.launch.py map_file:=/ros2_ws/maps/my_map.posegraph
```

## Visualization with Foxglove

1. Open Foxglove Studio
2. Connect to `ws://localhost:8765` (or your robot's IP)
3. Add panels to visualize:
   - **Map** - Topic: `/map` (nav_msgs/OccupancyGrid)
   - **Rfootprint` → `base_link`: 0.01m in z-axis (robot geometry)
- `base_link` → `laser`: 0.1m in z-axis, 180° rotation (sensor mounting)

Adjust if your LIDAR mounting differs.

**Complete TF Tree:**
```
map (from SLAM Toolbox when active)
  └─ odom (from Kobuki odometry)
      └─ base_footprint
          └─ base_link
              └─ laser
```olbox/graph_visualization` (optional)

## Configuration

### Mapping Parameters

Edit [config/mapper_params_online_async.yaml](config/mapper_params_online_async.yaml) to adjust:
- `resolution`: Map resolution in meters per pixel (default: 0.05)
- `max_laser_range`: Maximum LIDAR range in meters (default: 12.0)
- Loop closure settings
- Scan matching parameters

### Localization Parameters

Edit [config/mapper_params_localization.yaml](config/mapper_params_localization.yaml) to adjust:
- Localization accuracy
- Initial pose settings
- Scan matching sensitivity

### Frame Configuration

The transforms are configured in `sllidar_with_transform.launch.py`:
- `base_link` → `laser`: 0.1m in z-axis, 180° rotation (facing backward)

Adjust if your LIDAR mounting differs.
Saving Maps

There are three ways to save a map:

**1. Using the helper script (recommended):**
```bash
ros2 run slam save_map_helper.py
```

**2. Using service calls directly:**
```bash
# Save as SLAM Toolbox format (.posegraph)
ros2 service call /slam_toolbox/serialize_map slam_toolbox/srv/SerializePoseGraph \
  "{filename: '/ros2_ws/maps/my_map'}"

# Save as standard ROS map (.yaml/.pgm)
ros2 service call /slam_toolbox/save_map slam_toolbox/srv/SaveMap \
  "{name: {data: '/ros2_ws/maps/my_map'}}"
```

**3. From Foxglove:**
- Use the Service Call panel to call `/slam_toolbox/serialize_map`

### Other SLAM Controls

```bash
# Pause mapping (stop processing new scans)
ros2 service call /slam_toolbox/pause_new_measurements std_srvs/srv/Empty

# Resume mapping
ros2 service call /slam_toolbox/resume_new_measurements std_srvs/srv/Empty

# Clear the current map
ros2 service call /slam_toolbox/clear_queue std_srvs/srv/Empt
### Poor mapping quality
- Drive slowly and smoothly
- Ensure good LIDAR visibility (avoid transparent/reflective surfaces)
- Check `max_laser_range` setting matches your LIDAR specs
- Increase `minimum_travel_distance` for sparser maps

## Advanced Usage

### Manual Service Calls

You can also save maps using ROS2 services directly:

```bash
# Save as SLAM Toolbox format
ros2 service call /slam_toolbox/serialize_map slam_toolbox/srv/SerializePoseGraph \
  "{filename: '/ros2_ws/maps/my_map'}"

# Save as standard ROS map
ros2 service call /slam_toolbox/save_map slam_toolbox/srv/SaveMap \
  "{name: {data: '/ros2_ws/maps/my_map'}}"

# Pause mapping
ros2 service call /slam_toolbox/pause_new_measurements std_srvs/srv/Empty

# Resume mapping
ros2 service call /slam_toolbox/resume_new_measurements std_srvs/srv/Empty
```

### Running without xterm

If xterm is not available, modify `slam_mapping.launch.py` to remove the `prefix='xterm -e'` and run the controller manually in a separate terminal:

```bash
ros2 run slam slam_controller.py
```

## Map Storage

Maps are stored in the `maps/` directory at the project root. This directory is:
- Mounted as a Docker volume for persistence
- Ignored by git (except README.md)
- Shared between host and container

**Location in container:** `/ros2_ws/maps/`
**Location on host:** `./maps/`

## References

- [SLAM Toolbox Documentation](https://github.com/SteveMacenski/slam_toolbox)
- [SLAMTEC LIDAR ROS2 Driver](https://github.com/slamtec/sllidar_ros2)
- [Foxglove Studio](https://foxglove.dev/)

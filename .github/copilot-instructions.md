# Kobuki ROS2 Project - AI Agent Instructions

## Project Overview

This is a ROS2 Humble project for the Kobuki mobile robot base, extending the kobuki-base ecosystem with:

- Multi-container Docker architecture for modular deployment
- SLAM capabilities using SLAM Toolbox and SLAMTEC LIDAR
- Command velocity multiplexing for priority-based control switching
- Cross-platform support (ARM64/AMD64) with prebuilt containers

**Primary Components:**

- `kobuki/`: Main robot metapackage with launch files
- `kobuki_ros/`: Upstream kobuki packages (node, description, drivers, controllers)
- `kobuki_core/`: Low-level hardware interface and FTDI drivers
- `cmd_vel_mux/`: Priority-based velocity command multiplexer
- `slam/`: LIDAR integration and SLAM Toolbox configuration
- `augs_bringup/`: Simplified bringup package without joystick dependencies

## Architecture Patterns

### Multi-Container Design

Services communicate via **CycloneDDS** on a shared Docker bridge network (`ros_network`):

- `kobuki` service: Robot base controller and hardware interface
- `lidar_node` service: LIDAR driver, SLAM, and Foxglove visualization
- Configuration: [cyclonedds.xml](../cyclonedds.xml) defines peer discovery and message size limits

**Example from [compose.yaml](../compose.yaml):**

```yaml
environment:
  - RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
  - CYCLONEDDS_URI=file:///cyclonedds.xml
volumes:
  - ./cyclonedds.xml:/cyclonedds.xml
```

### TF Tree Convention

Critical transform hierarchy requiring careful management:

```
odom → base_footprint → base_link → laser
```

**Key Issue:** `kobuki_node` publishes `odom→base_footprint`, but `kobuki_description` URDF defines `base_link→base_footprint` (backwards). Solution: Manually publish static transform `base_footprint→base_link` with 10.2mm vertical offset.

**Pattern in all launch files:**

```python
Node(
    package='tf2_ros',
    executable='static_transform_publisher',
    arguments=['0', '0', '0.0102', '0', '0', '0', 'base_footprint', 'base_link']
)
```

### Launch File Composition

Use `IncludeLaunchDescription` pattern extensively to compose modular launch files:

**Example from [kobuki.launch.py](../kobuki/launch/kobuki.launch.py):**

```python
kobuki_node_launch = IncludeLaunchDescription(
    PythonLaunchDescriptionSource(os.path.join(
        get_package_share_directory('kobuki_node'), 'launch', 'kobuki_node_mux.launch.py'
    )),
    launch_arguments={'publish_tf': 'true'}.items()
)
```

Typical launch hierarchy:

- Top-level metapackage launch → Component launches → Node configurations
- Pass parameters via `launch_arguments` dict

## Development Workflows

### Docker Build Chain

Three Dockerfile layers for progressive builds:

1. **Base**: [docker/Dockerfile](../docker/Dockerfile) - Core kobuki packages
2. **Bringup**: [bringup.Dockerfile](../bringup.Dockerfile) - Extends base with augs_bringup
3. **SLAM**: [slam.Dockerfile](../slam.Dockerfile) - Extends bringup with LIDAR/SLAM stack

**Build pattern:**

```bash
# Development build with local changes
docker compose -f compose.yaml build

# Run multi-service stack
docker compose up -d

# Execute commands in running containers
docker exec -it collabs-kobuki-lidar_node-1 bash
```

### Build System

Standard ROS2 colcon workflow with workspace at `/kobuki` (in containers) or workspace root (local):

```bash
# Source ROS2 and build
source /opt/ros/humble/setup.bash
colcon build --symlink-install

# Source workspace overlay after building
source install/setup.bash
```

**Symlink install** used in development Dockerfiles to avoid rebuilds for Python launch files.

### SLAM Workflow

Interactive mapping and localization via helper scripts:

**Mapping:**

```bash
ros2 launch slam slam_mapping.launch.py  # Start mapping
ros2 run slam save_map_helper.py          # Save map when ready
```

**Localization:**

```bash
ros2 launch slam slam_localization.launch.py  # Interactive map selector
```

Maps stored in `maps/` directory with `.posegraph`, `.yaml`, `.pgm` files.

## Critical Conventions

### cmd_vel_mux Priority System

Control sources defined in [cmd_vel_mux_params.yaml](../cmd_vel_mux/config/cmd_vel_mux_params.yaml):

- **Priority 10**: `mux/input/joystick` (teleoperation, 0.1s timeout)
- **Priority 1**: `mux/input/navigation` (autonomous nav, 0.5s timeout)
- **Priority 0**: `mux/input/default` (fallback, 0.1s timeout)

Higher priority sources **automatically preempt** lower ones. Add new sources via `/cmd_vel_mux/set_parameters_atomically` service.

### Package Naming

- Upstream packages: `kobuki_*` (e.g., `kobuki_node`, `kobuki_description`)
- Custom packages: descriptive names (`slam`, `cmd_vel_mux`, `augs_bringup`)
- Launch files: `<purpose>.launch.py` (e.g., `slam_mapping.launch.py`)

### Device Mapping

Critical udev rules and device paths:

- **Kobuki base**: `/dev/kobuki` (via `60-kobuki.rules`)
- **LIDAR**: `/dev/rplidar` (requires privileged mode or device mapping)

In Docker, map with `devices:` or use `privileged: true`.

## Integration Points

### External Dependencies

- **GitHub repositories**: `AIResearchLab/kobuki` and `AIResearchLab/kobuki_dependencies` (cloned in Dockerfile)
- **SLAM Toolbox**: ROS2 package, configured via YAML in `slam/config/`
- **sllidar_ros2**: SLAMTEC driver, cloned at build time
- **Foxglove Bridge**: WebSocket server on port 8765 for visualization

### Cross-Package Communication

- `kobuki_node` publishes to `/odom`, `/joint_states`, odometry TF
- `cmd_vel_mux` subscribes to multiple `/mux/input/*` topics, publishes `/mux/output/cmd_vel`
- Launch files pass `/mux/output/cmd_vel` to `kobuki_node` remapping

## Testing and Debugging

### Hardware Connectivity Check

```bash
kobuki-version-info  # Non-ROS tool to verify USB connection
```

Expected output shows hardware/firmware versions and device ID.

### Common Issues

1. **TF tree breaks**: Ensure static transform `base_footprint→base_link` is published
2. **Multi-container communication fails**: Verify CycloneDDS peers in [cyclonedds.xml](../cyclonedds.xml) match service names
3. **Device not found**: Check udev rules installation and cable reconnection after rule updates

### Visualization

Use Foxglove Studio connecting to `ws://localhost:8765` to view:

- `/map` topic (SLAM output)
- `/scan` topic (LIDAR data)
- TF tree visualization

## File Organization

```
<package>/
├── launch/           # Python launch files
├── config/           # YAML parameter files
├── urdf/             # Robot description (use xacro)
├── scripts/          # Python executables (chmod +x, #!/usr/bin/env python3)
├── package.xml       # ROS2 package manifest
└── CMakeLists.txt    # Build configuration (install launch/, config/, scripts/)
```

Always install non-code resources in CMakeLists.txt:

```cmake
install(DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME})
```

## Project-Specific Commands

```bash
# Pull and run prebuilt containers
docker compose pull && docker compose up

# Build from source and run
docker compose -f compose.yaml build && docker compose up

# Access running container for debugging
docker exec -it collabs-kobuki-kobuki-1 bash

# Check ROS2 topics in multi-container setup
docker exec -it collabs-kobuki-lidar_node-1 ros2 topic list

# Save SLAM map from running session
docker exec -it collabs-kobuki-lidar_node-1 ros2 run slam save_map_helper.py
```

## When Adding New Features

1. **New control source**: Update `cmd_vel_mux_params.yaml` with priority and timeout
2. **New sensor**: Add to URDF, create static transform if needed, update relevant launch file
3. **New Docker service**: Add to `compose.yaml`, update CycloneDDS peers list
4. **New package**: Follow ROS2 package structure, add to colcon workspace, update Dockerfile if needed

# Project Context: Kobuki ROS2 Robotics Platform

## Project Summary

This repository contains a ROS2 Humble implementation for the Kobuki mobile robot base, merging and extending upstream kobuki-base repositories with modern features including Docker containerization, SLAM capabilities, and multi-platform support.

## Key Work Completed

### 1. Multi-Container Architecture
- **Separated concerns**: Kobuki base controller and LIDAR/SLAM stack run in separate Docker containers
- **CycloneDDS Integration**: Custom configuration for reliable multi-container ROS2 communication
- **Network Design**: Shared bridge network with peer discovery configuration
- **Files**: [compose.yaml](compose.yaml), [cyclonedds.xml](cyclonedds.xml)

### 2. Docker Build System
Three-tier Dockerfile architecture for progressive feature addition:

**Base Layer** ([docker/Dockerfile](docker/Dockerfile)):
- ROS2 Humble on Ubuntu Jammy
- Core dependencies (angles, diagnostics, joint-state-publisher)
- Kobuki packages from AIResearchLab GitHub repositories
- FTDI udev rules for USB device recognition
- Multi-architecture support (ARM64/AMD64)

**Bringup Layer** ([bringup.Dockerfile](bringup.Dockerfile)):
- Extends base with simplified bringup package
- Removes joystick dependencies for headless deployment
- Adds custom TF transform handling

**SLAM Layer** ([slam.Dockerfile](slam.Dockerfile)):
- Adds SLAMTEC LIDAR driver (sllidar_ros2)
- Integrates SLAM Toolbox for mapping and localization
- Foxglove Bridge for web-based visualization
- Custom slam package with helper scripts

### 3. Transform Tree Management
Resolved critical TF tree inconsistency between kobuki_node and kobuki_description:

**Problem**: kobuki_node publishes `odom→base_footprint`, but URDF defines inverse relationship
**Solution**: Static transform publisher in all launch files (`base_footprint→base_link` with 10.2mm offset)
**Implementation**: Consistent pattern across [augs_bringup](augs_bringup/launch/augs_kobuki_node.launch.py), [kobuki](kobuki/launch/kobuki.launch.py), and SLAM launch files

### 4. Command Velocity Multiplexer
Priority-based control switching system using cmd_vel_mux:

- **Joystick control**: Priority 10 (highest) for manual override
- **Navigation stack**: Priority 1 for autonomous operation
- **Default input**: Priority 0 as fallback
- **Auto-preemption**: Higher priority sources automatically take control
- **Dynamic reconfiguration**: Service-based subscriber addition/removal
- **Configuration**: [cmd_vel_mux_params.yaml](cmd_vel_mux/config/cmd_vel_mux_params.yaml)

### 5. SLAM System Implementation
Complete mapping and localization workflow:

**Components**:
- [sllidar_with_transform.launch.py](slam/launch/sllidar_with_transform.launch.py): LIDAR driver + TF + Foxglove
- [slam_mapping.launch.py](slam/launch/slam_mapping.launch.py): Interactive mapping mode
- [slam_localization.launch.py](slam/launch/slam_localization.launch.py): Localization with map selection

**Helper Scripts**:
- `save_map_helper.py`: Interactive map saving interface
- `map_selector.py`: Browse and select maps for localization
- `slam_controller.py`: Mapping status display

**Map Storage**: [maps/](maps/) directory with `.posegraph`, `.yaml`, `.pgm` formats

### 6. Launch File Patterns
Established modular launch composition using `IncludeLaunchDescription`:

**Pattern**:
- Top-level metapackage launches (e.g., `kobuki.launch.py`)
- Include component-specific launches from packages
- Pass configuration via `launch_arguments`
- Consistent argument propagation (`publish_tf`, `use_sim_time`, etc.)

**Examples**:
- [kobuki.launch.py](kobuki/launch/kobuki.launch.py): Combines node, joyop, description, cmd_vel_mux
- [slam_mapping.launch.py](slam/launch/slam_mapping.launch.py): LIDAR + SLAM Toolbox + status display

### 7. Package Organization

**Custom Packages Created**:
- `kobuki/`: Metapackage with top-level launch files
- `slam/`: LIDAR integration and SLAM configuration
- `augs_bringup/`: Simplified bringup without joystick dependencies
- `cmd_vel_mux/`: Velocity command multiplexer (forked and merged improvements)

**Upstream Integration**:
- `kobuki_ros/`: Collection of official kobuki packages
- `kobuki_core/`: Hardware drivers and interfaces
- `kobuki_ros_interfaces/`: Message/action definitions
- `kobuki_velocity_smoother/`: Acceleration limiting

### 8. Development Workflows

**Local Development**:
```bash
colcon build --symlink-install
source install/setup.bash
```

**Docker Development**:
```bash
docker compose build
docker compose up -d
docker exec -it <container> bash
```

**SLAM Mapping**:
```bash
ros2 launch slam slam_mapping.launch.py
ros2 run slam save_map_helper.py
```

**SLAM Localization**:
```bash
ros2 launch slam slam_localization.launch.py
```

### 9. Visualization and Monitoring
- **Foxglove Bridge**: WebSocket server on port 8765
- **Real-time topics**: `/map`, `/scan`, `/odom`, TF tree
- **Diagnostic tools**: `kobuki-version-info`, `kobuki-simple-keyop`
- **Active mux status**: Published on `/active` topic

### 10. Configuration Management

**CycloneDDS** ([cyclonedds.xml](cyclonedds.xml)):
- Explicit peer discovery between containers
- 65500B max message size for LIDAR data
- Shared volume mount across all services

**Parameter Files**:
- SLAM Toolbox configs: [mapper_params_online_async.yaml](slam/config/mapper_params_online_async.yaml), [mapper_params_localization.yaml](slam/config/mapper_params_localization.yaml)
- Cmd vel mux: [cmd_vel_mux_params.yaml](cmd_vel_mux/config/cmd_vel_mux_params.yaml)

## Technical Decisions

### Why Multi-Container?
- **Modularity**: SLAM stack optional, can run base system independently
- **Resource isolation**: LIDAR processing separated from real-time control
- **Development flexibility**: Rebuild only changed components

### Why CycloneDDS?
- **Multi-container support**: Better peer discovery than default FastRTPS
- **Performance**: Lower latency for LIDAR data streams
- **Configuration**: Explicit peer list prevents discovery issues

### Why Static TF Transform?
- **URDF incompatibility**: Upstream kobuki_description can't be easily modified (external dependency)
- **kobuki_node behavior**: TF publishing tied to odometry updates
- **Simplicity**: Static transform simpler than patching URDF chain

## Dependencies

**ROS2 Packages**:
- `ros-humble-angles`, `ros-humble-diagnostics`, `ros-humble-joint-state-publisher`
- `ros-humble-slam-toolbox`, `ros-humble-foxglove-bridge`
- `ros-humble-rmw-cyclonedds-cpp`

**External Repositories**:
- [AIResearchLab/kobuki](https://github.com/AIResearchLab/kobuki)
- [AIResearchLab/kobuki_dependencies](https://github.com/AIResearchLab/kobuki_dependencies)
- [slamtec/sllidar_ros2](https://github.com/slamtec/sllidar_ros2)

**Hardware**:
- Kobuki mobile base (USB/FTDI connection at `/dev/kobuki`)
- SLAMTEC LIDAR (serial connection at `/dev/rplidar`)

## Current Status

**Working Features**:
- ✅ Multi-container Docker deployment
- ✅ Robot base control and odometry
- ✅ Priority-based velocity command multiplexing
- ✅ LIDAR data acquisition
- ✅ SLAM mapping and map saving
- ✅ SLAM localization with map selection
- ✅ Foxglove visualization
- ✅ Joystick teleoperation
- ✅ Multi-architecture container builds (ARM64/AMD64)

**Known Issues**:
- TF tree requires manual static transform (upstream URDF issue)
- Device paths require udev rules and cable reconnection
- Privileged mode needed for device access in Docker

## Future Enhancements

Potential areas for extension:
- Navigation stack integration (Nav2)
- Autonomous exploration algorithms
- Multi-robot coordination
- RViz2 integration alongside Foxglove
- CI/CD pipeline for container builds
- Parameter tuning for specific environments

## Documentation Resources

- Main README: [README.md](README.md)
- SLAM package docs: [slam/README.md](slam/README.md)
- Cmd vel mux docs: [cmd_vel_mux/README.md](cmd_vel_mux/README.md)
- Map storage: [maps/README.md](maps/README.md)
- AI agent guide: [.github/copilot-instructions.md](.github/copilot-instructions.md)

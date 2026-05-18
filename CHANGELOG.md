# Changelog

## 2026-05-18

- **fix:** `slam/config/nav2_params.yaml` — reconcile bt_navigator `plugin_lib_names` against plugins actually present in the ROS2 Humble install; removed `nav2_path_expiring_timer_condition_bt_node`, `nav2_speed_limit_action_bt_node`, `nav2_stopped_condition_bt_node` (do not exist in Humble); corrected 7 renamed plugins (`nav2_nav_to_pose_action_bt_node` → `nav2_navigate_to_pose_action_bt_node`, `nav2_cancel_*` → `nav2_*_cancel` pattern, etc.)

## 2026-04-14

- **fix:** `slam/config/nav2_params.yaml` — lifecycle_manager `node_names` already trimmed to 4 essential nodes (controller_server, planner_server, behavior_server, bt_navigator); `smoother_server` and `waypoint_follower` excluded to prevent lifecycle chain stall on startup
- **fix:** `orchestrator/robot_orchestrator.py` — removed unused `map:=` argument from `/autonomy/start`; `navigation_launch.py` does not use this arg (map is published directly by SLAM Toolbox localization)
- **feat:** `orchestrator/robot_orchestrator.py` — added `wait_for_nav2_ready()` method; `/autonomy/start` now polls lifecycle nodes for up to 30s and returns a distinct `"still initializing"` response if they haven't all reached `active`
- **fix:** `orchestrator/robot_orchestrator.py` — `send_goal` timeout increased 5s → 10s; error message now includes live Nav2 lifecycle states so failures are self-diagnosing

# Kobuki Orchestrator — API Quick Reference

Base URL: `http://<pi-ip>:8080`
Interactive docs: `http://<pi-ip>:8080/docs`  (Swagger UI, auto-generated)

---

## Status

| Method | Endpoint   | Description                        |
|--------|------------|------------------------------------|
| GET    | /status    | Full robot state snapshot          |
| GET    | /maps      | List saved maps and annotation files |

---

## Joystick

| Method | Endpoint        | Description                                                |
|--------|-----------------|------------------------------------------------------------|
| POST   | /joystick/start | Start joystick teleop launch (overlay process, no mode change) |
| POST   | /joystick/stop  | Stop joystick teleop launch (idempotent, no mode change) |

Launch behavior:
- `/joystick/start` uses package/file launch form through the orchestrator helper: `ros2 launch slam joy_teleop.launch.py`.
- Launch target is configurable via `JOYSTICK_LAUNCH_PKG` and `JOYSTICK_LAUNCH_FILE` environment variables.

---

## Mapping

| Method | Endpoint        | Body                  | Description                          |
|--------|-----------------|-----------------------|--------------------------------------|
| POST   | /mapping/start  | —                     | Launch SLAM in mapping mode          |
| POST   | /mapping/stop   | `{"name": "my_map"}`  | Save map and stop SLAM               |
| POST   | /mapping/save   | `{"name": "my_map"}`  | Checkpoint save (keep mapping)        |

**Typical workflow:**
```
POST /mapping/start
  ... drive around with teleop ...
POST /mapping/stop   {"name": "living_room"}
```

---

## Localization

| Method | Endpoint                        | Body                                          | Description                          |
|--------|---------------------------------|-----------------------------------------------|--------------------------------------|
| POST   | /localization/start             | `{"name": "my_map"}`                          | Load map, start SLAM localizer       |
| POST   | /localization/set_initial_pose  | `{"x":0.0,"y":0.0,"yaw":0.0,"covariance":0.5}` | Seed pose estimate for convergence   |

---

## Annotations

| Method | Endpoint                          | Body / Param        | Description                              |
|--------|-----------------------------------|---------------------|------------------------------------------|
| POST   | /annotations/load                 | `{"name":"my_map"}` | Load <name>.annotations.json from maps/  |
| GET    | /annotations/waypoints            | —                   | List loaded waypoints                    |
| POST   | /annotations/save                 | Full annotation JSON | Write annotation file to maps/           |

**Annotation file format** (`maps/my_map_name.annotations.json`):
```json
{
  "map": "my_map_name",
  "waypoints": [
    { "name": "kitchen", "x": 1.2, "y": 0.5, "yaw": 0.0 }
  ],
  "dock": { "x": 0.0, "y": 0.0, "yaw": 3.14159 }
}
```

---

## Autonomy (Nav2)

| Method | Endpoint        | Body | Description                                        |
|--------|-----------------|------|----------------------------------------------------|
| POST   | /autonomy/start | —    | Start Nav2 stack (requires localization running)   |
| POST   | /autonomy/stop  | —    | Stop Nav2, cancel goals                            |

---

## Navigation

| Method | Endpoint                          | Body / Param                          | Description                          |
|--------|-----------------------------------|---------------------------------------|--------------------------------------|
| POST   | /navigation/goto                  | `{"x":1.2,"y":0.5,"yaw":0.0}`        | Send pose goal to Nav2               |
| POST   | /navigation/goto_waypoint/{name}  | path param: waypoint name             | Navigate to named waypoint           |
| POST   | /navigation/cancel                | —                                     | Cancel current goal                  |
| GET    | /navigation/status                | —                                     | Check active goal status             |

---

## Dock

| Method | Endpoint      | Description                                               |
|--------|---------------|-----------------------------------------------------------|
| POST   | /dock/return  | Navigate to dock pose (from annotations) then auto-dock   |
| POST   | /dock/trigger | Trigger Kobuki IR auto-dock sequence from current position |

---

## Utilities

| Method | Endpoint        | Description                              |
|--------|-----------------|------------------------------------------|
| POST   | /costmap/clear  | Clear Nav2 global costmap                |
| POST   | /estop          | Kill everything, cancel goals immediately |

---

## Robot Modes (state machine)

Joystick control is an overlay process. Calling `/joystick/start` or `/joystick/stop`
does not transition the robot mode and can be used while in `IDLE`, `MAPPING`,
`LOCALIZING`, or `AUTONOMOUS`.

```
         /mapping/start (from any state except MAPPING)
IDLE ─────────────────────► MAPPING
  ▲                              │
  │         /mapping/stop        │
  │◄─────────────────────────────┘
  │
  │   /localization/start (from any state — kills mapping & nav2)
  ├───────────────────────► LOCALIZING
  │                              │
  │  /autonomy/start             │
  │  (from LOCALIZING or IDLE)   │
  │                              ▼
  │                         AUTONOMOUS
  │    /autonomy/stop            │ │
  │    ┌─────────────────────────┘ │
  │    ▼                           │
  │  LOCALIZING (if still running) │
  │  or IDLE (otherwise)           │
  │                                │
  │       /dock/return             │
  │                                ▼
  │◄──────────────── RETURNING_TO_DOCK
  │
  │   /estop (from any state)
  └◄──────────────────────────── *
```

---

## Example: Full session from scratch

```bash
PI=192.168.1.100

# 1. Map the environment
#    Start joystick teleop overlay so the operator can drive.
curl -X POST $PI:8080/joystick/start
curl -X POST $PI:8080/mapping/start
#    ... drive with teleop ...
curl -X POST $PI:8080/mapping/stop -H 'Content-Type: application/json' \
     -d '{"name":"living_room"}'

#    Stop joystick if no longer needed.
curl -X POST $PI:8080/joystick/stop

# 2. Define waypoints (or edit the JSON file directly)
curl -X POST $PI:8080/annotations/save -H 'Content-Type: application/json' \
     -d @my_map_name.annotations.json

# 3. Localize and start autonomy
curl -X POST $PI:8080/localization/start -H 'Content-Type: application/json' \
     -d '{"name":"living_room"}'
curl -X POST $PI:8080/localization/set_initial_pose -H 'Content-Type: application/json' \
     -d '{"x":0.0,"y":0.0,"yaw":0.0}'
curl -X POST $PI:8080/annotations/load -H 'Content-Type: application/json' \
     -d '{"name":"living_room"}'
curl -X POST $PI:8080/autonomy/start

# 4. Navigate
curl -X POST $PI:8080/navigation/goto_waypoint/kitchen

# 5. Check status
curl $PI:8080/navigation/status
curl $PI:8080/status

# 6. Go home
curl -X POST $PI:8080/dock/return
```

Notes:
- Joystick control is implemented as an overlay process and does not transition robot mode.
- `/status` includes process information so you can verify whether `joystick` is running.

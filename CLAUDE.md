# collabs-kobuki — Kobuki-based autonomous robot

This repo is the ROS 2 stack for Gus's Kobuki-based autonomous mobile robot (Raspberry Pi 5, ROS 2 Humble in Docker, SLAM Toolbox, Nav2-bound, FastAPI orchestrator).

## Wiki — read this first for orientation

There is a separate knowledge base for this project at:

```
/Users/agus/Documents/Claude/Projects/Turtlebot 2 Autonomous Robot/Wiki/
```

Before answering about hardware, the power system, SLAM, the orchestrator, visualization, or "why did we do X", read:

- `Wiki/README.md` — curated map of content. Start here.
- `Wiki/CLAUDE.md` — LLM-specific orientation (folder semantics, status conventions, hard rules).

The wiki is authoritative about **context, history, and why**. The code in this repo is authoritative about **current implementation**. If a wiki note contradicts the code, treat the wiki as potentially stale — flag it so Gus can update, don't silently follow it.

## Wiki folders

- `topics/hardware/`, `topics/power/`, `topics/software/` — how things work. One concept per file.
- `topics/recipes/` — copy-pasteable commands.
- `topics/troubleshooting/` — symptom → cause → fix.
- `decisions/` — why a choice was made. Numbered, immutable (supersede rather than edit).
- `journal/` — dated notes (currently sparse).
- `attachments/` — images referenced by notes.

## Workflow

When you finish a substantive piece of work in this repo, run the `/wiki-update` slash command to propose wiki updates. **Do not update the wiki silently** — propose the diff first, let Gus review, then write.

Small commits and routine refactors do not require wiki updates. Reserve updates for new concepts, solved problems, and non-obvious decisions.

## Hard rules

- **The dual-rail power architecture is planned, not built.** See `Wiki/topics/power/power-architecture.md` — status is `planned`. The current live power is the ad-hoc USB-splitter setup. Do not write or speak as if the dual-rail is installed.
- **Do not invent ROS 2 commands.** If a recipe isn't in `Wiki/topics/recipes/` or clearly in the repo, say so rather than guessing.
- **Interactive verification before implementation** is Gus's preferred working style — prefer `ros2 topic echo` / `ros2 topic info` checks over speculative code.
- **Production-ready file delivery.** No pseudocode, no partial examples — complete files.
- **Markdown + Mermaid** for all documentation.

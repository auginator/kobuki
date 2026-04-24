---
description: Propose updates to the Turtlebot wiki based on this session's work
---

We just finished a chunk of work in this repo. Read the project wiki at:

```
/Users/agus/Documents/Claude/Projects/Turtlebot 2 Autonomous Robot/Wiki/
```

Start with `Wiki/README.md` and `Wiki/CLAUDE.md` to orient on the structure and conventions. Then propose updates that capture any **reusable knowledge** from this session.

## Focus on

1. **New or updated topic notes** — if a concept now works differently, update the relevant file in `Wiki/topics/`. If a new concept emerged, draft a new note (kebab-case filename, same frontmatter + one-liner + sections as the existing notes).

2. **Troubleshooting notes** — if we hit a problem and figured out the cause, add an entry in `Wiki/topics/troubleshooting/`. Lead with the symptom, then cause, then fix. These are the highest-ROI notes.

3. **Decision records** — if we made a non-obvious choice (picked X over Y, or committed to an approach with real tradeoffs), draft a new numbered decision in `Wiki/decisions/` (`NNN-short-name.md`, next number in sequence). Decisions are immutable — if we changed our mind about a prior decision, write a new one that supersedes.

4. **Recipes** — new copy-pasteable command sequences go in `Wiki/topics/recipes/`.

## Ignore

- Implementation details derivable from reading the code.
- Ephemeral debugging state that won't matter next week.
- Small refactors with no conceptual change.
- Commit-log-level detail. The git history covers that.

## Output format

1. **List** the files you propose to add or change, with one-line rationales.
2. **Show** the full contents (for new files) or exact diff (for existing files) of each change.
3. **Wait** for my go-ahead before writing. Do not write anything to disk until I approve.

If nothing surprising happened in this session, say so and skip the update. The wiki is for reusable knowledge, not a commit log.

## Cross-reference

When you add or edit notes, also update `Wiki/README.md` if a new file needs to be linked, and update the `updated:` frontmatter field on any file you touched. An unlinked file is invisible to this wiki.

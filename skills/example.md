---
name: example
description: An example skill template — customize or replace this
modes: []
---

## Instructions

This is an example skill file. Skills are markdown files with YAML frontmatter.

### Frontmatter fields:
- `name`: Unique skill identifier
- `description`: When to use this skill (shown to the LLM)
- `modes`: List of modes where this skill is available (empty = all modes)

### How skills work:
1. Skill names and descriptions are included in the system prompt
2. Before responding, the LLM checks if any skill matches the user's request
3. If matched, the LLM loads the full skill instructions
4. The skill provides step-by-step procedures for the task

### Skill locations (priority order):
1. `.mini-agent/skills/` — Project-level (highest priority)
2. `~/.mini-agent/skills/` — Global user skills
3. Built-in skills — Ship with mini-agent

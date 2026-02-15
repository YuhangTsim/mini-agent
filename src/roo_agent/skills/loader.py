"""Skill file loader — parses markdown with YAML frontmatter."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import frontmatter


@dataclass
class Skill:
    name: str
    description: str = ""
    modes: list[str] = field(default_factory=list)  # Empty = all modes
    content: str = ""  # The full markdown instructions
    file_path: str = ""

    @property
    def summary(self) -> dict[str, str]:
        """Return name + description for prompt injection."""
        return {"name": self.name, "description": self.description}


def load_skill(path: Path) -> Skill:
    """Load a skill from a markdown file with YAML frontmatter."""
    post = frontmatter.load(str(path))

    name = post.metadata.get("name", path.stem)
    description = post.metadata.get("description", "")
    modes = post.metadata.get("modes", [])
    if isinstance(modes, str):
        modes = [m.strip() for m in modes.split(",")]

    return Skill(
        name=name,
        description=description,
        modes=modes,
        content=post.content,
        file_path=str(path),
    )

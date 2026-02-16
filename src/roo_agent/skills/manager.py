"""Skills manager — discovery, loading, and mode filtering."""

from __future__ import annotations

from pathlib import Path

from .loader import Skill, load_skill


class SkillsManager:
    """Discovers and manages skills from multiple directories."""

    def __init__(self, search_dirs: list[Path] | None = None):
        self._skills: dict[str, Skill] = {}
        self._search_dirs = search_dirs or []
        # Always include built-in skills
        builtin_dir = Path(__file__).parent.parent / "skills" / "builtin"
        if builtin_dir.exists():
            self._search_dirs.append(builtin_dir)

    def discover(self) -> None:
        """Scan all search directories and load skills."""
        self._skills.clear()
        for search_dir in self._search_dirs:
            if not search_dir.exists():
                continue
            for path in search_dir.glob("*.md"):
                try:
                    skill = load_skill(path)
                    # Later entries override earlier (project > global > builtin)
                    self._skills[skill.name] = skill
                except Exception:
                    continue  # Skip malformed skill files

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def get_for_mode(self, mode_slug: str) -> list[Skill]:
        """Get skills available in the given mode."""
        result = []
        for skill in self._skills.values():
            if not skill.modes or mode_slug in skill.modes:
                result.append(skill)
        return result

    def all_skills(self) -> list[Skill]:
        return list(self._skills.values())

    def get_summaries_for_mode(self, mode_slug: str) -> list[dict[str, str]]:
        """Get name+description summaries for prompt injection."""
        return [s.summary for s in self.get_for_mode(mode_slug)]

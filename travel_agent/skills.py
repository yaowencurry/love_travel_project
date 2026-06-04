from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Skill:
    name: str
    path: Path
    triggers: tuple[str, ...]
    content: str


class SkillRegistry:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self._skills = self._load()

    def all(self) -> list[Skill]:
        return list(self._skills)

    def match(self, task: str) -> Skill | None:
        normalized = task.strip().lower()
        for skill in self._skills:
            if normalized in skill.triggers:
                return skill
        return None

    def _load(self) -> list[Skill]:
        if not self.root.exists():
            return []

        skills: list[Skill] = []
        for skill_path in sorted(self.root.glob("*/SKILL.md")):
            content = skill_path.read_text(encoding="utf-8")
            triggers = self._parse_triggers(content)
            skills.append(
                Skill(
                    name=skill_path.parent.name,
                    path=skill_path,
                    triggers=tuple(triggers),
                    content=content,
                )
            )
        return skills

    @staticmethod
    def _parse_triggers(content: str) -> list[str]:
        for line in content.splitlines():
            if line.lower().startswith("triggers:"):
                return [
                    item.strip().lower()
                    for item in line.split(":", 1)[1].split(",")
                    if item.strip()
                ]
        return []


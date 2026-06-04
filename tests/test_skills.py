from pathlib import Path

from travel_agent.skills import SkillRegistry


def test_skill_registry_discovers_and_matches_skill_by_trigger() -> None:
    registry = SkillRegistry(Path("skills"))

    skill = registry.match("quote_hotels")

    assert skill is not None
    assert skill.name == "hotel_selection"
    assert "酒店" in skill.content


def test_skill_registry_returns_none_for_unknown_task() -> None:
    registry = SkillRegistry(Path("skills"))

    assert registry.match("unknown_task") is None


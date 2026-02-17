"""Tests for roo_agent.core.mode: ModeConfig, BUILTIN_MODES, get_mode."""

from __future__ import annotations

import re

import pytest

from roo_agent.core.mode import BUILTIN_MODES, ModeConfig, get_mode, list_modes


class TestBuiltinModes:
    def test_has_five_modes(self):
        assert len(BUILTIN_MODES) == 5

    def test_required_modes_present(self):
        expected = {"code", "plan", "ask", "debug", "orchestrator"}
        assert set(BUILTIN_MODES.keys()) == expected

    def test_code_mode_tool_groups(self):
        mode = BUILTIN_MODES["code"]
        assert "read" in mode.tool_groups
        assert "edit" in mode.tool_groups
        assert "command" in mode.tool_groups

    def test_plan_mode_has_file_restrictions(self):
        mode = BUILTIN_MODES["plan"]
        assert "edit" in mode.file_restrictions
        restriction = mode.file_restrictions["edit"]
        # Must allow .md and .txt files
        assert re.search(restriction, "README.md")
        assert re.search(restriction, "notes.txt")
        # Must block .py files
        assert not re.search(restriction, "main.py")

    def test_plan_mode_no_command_group(self):
        mode = BUILTIN_MODES["plan"]
        assert "command" not in mode.tool_groups

    def test_ask_mode_read_only(self):
        mode = BUILTIN_MODES["ask"]
        assert "read" in mode.tool_groups
        assert "edit" not in mode.tool_groups
        assert "command" not in mode.tool_groups

    def test_debug_mode_has_read_edit_command(self):
        mode = BUILTIN_MODES["debug"]
        assert "read" in mode.tool_groups
        assert "edit" in mode.tool_groups
        assert "command" in mode.tool_groups

    def test_orchestrator_no_tool_groups(self):
        mode = BUILTIN_MODES["orchestrator"]
        assert mode.tool_groups == []

    def test_all_modes_have_role_definition(self):
        for slug, mode in BUILTIN_MODES.items():
            assert mode.role_definition, f"Mode '{slug}' missing role_definition"

    def test_all_modes_have_when_to_use(self):
        for slug, mode in BUILTIN_MODES.items():
            assert mode.when_to_use, f"Mode '{slug}' missing when_to_use"

    def test_all_modes_slug_matches_key(self):
        for key, mode in BUILTIN_MODES.items():
            assert mode.slug == key

    def test_all_modes_have_name(self):
        for slug, mode in BUILTIN_MODES.items():
            assert mode.name, f"Mode '{slug}' missing name"

    def test_mode_config_is_correct_type(self):
        for mode in BUILTIN_MODES.values():
            assert isinstance(mode, ModeConfig)


class TestGetMode:
    def test_get_existing_mode_returns_mode_config(self):
        mode = get_mode("code")
        assert isinstance(mode, ModeConfig)

    def test_get_code_mode(self):
        mode = get_mode("code")
        assert mode.slug == "code"

    def test_get_plan_mode(self):
        mode = get_mode("plan")
        assert mode.slug == "plan"

    def test_get_ask_mode(self):
        mode = get_mode("ask")
        assert mode.slug == "ask"

    def test_get_debug_mode(self):
        mode = get_mode("debug")
        assert mode.slug == "debug"

    def test_get_orchestrator_mode(self):
        mode = get_mode("orchestrator")
        assert mode.slug == "orchestrator"

    def test_get_unknown_mode_raises_key_error(self):
        with pytest.raises(KeyError, match="Unknown mode"):
            get_mode("nonexistent_mode")

    def test_get_unknown_lists_available(self):
        with pytest.raises(KeyError) as exc_info:
            get_mode("bogus")
        assert "code" in str(exc_info.value)


class TestListModes:
    def test_returns_five_modes(self):
        modes = list_modes()
        assert len(modes) == 5

    def test_all_are_mode_config(self):
        for mode in list_modes():
            assert isinstance(mode, ModeConfig)

    def test_contains_all_slugs(self):
        slugs = {m.slug for m in list_modes()}
        assert slugs == {"code", "plan", "ask", "debug", "orchestrator"}

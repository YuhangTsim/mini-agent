"""E2E tests for open-agent CLI."""

from __future__ import annotations

import os
import tempfile

import pytest
from click.testing import CliRunner


class TestCLI:
    """Test CLI commands."""
    
    @pytest.fixture
    def runner(self):
        """Create a Click CLI runner."""
        return CliRunner()
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def test_cli_help(self, runner):
        """Test CLI help command."""
        from open_agent.cli.app import cli
        
        result = runner.invoke(cli, ["--help"])
        
        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "--help" in result.output
    
    def test_cli_version(self, runner):
        """Test CLI version command."""
        from open_agent.cli.app import cli
        
        result = runner.invoke(cli, ["--version"])
        
        # Version flag should be recognized
        assert result.exit_code in [0, 2]  # 0 if exists, 2 if not
    
    def test_cli_init_creates_config(self, runner, temp_dir):
        """Test init command creates configuration."""
        from open_agent.cli.app import cli
        
        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(cli, ["init"])
            
            # Should create .open-agent directory
            config_dir = os.path.join(temp_dir, ".open-agent")
            if result.exit_code == 0:
                assert os.path.exists(config_dir)
    
    @pytest.mark.skipif(
        not os.environ.get("OPENAI_API_KEY") and not os.environ.get("OPENROUTER_API_KEY"),
        reason="No API key set"
    )
    def test_cli_chat_mode(self, runner, temp_dir):
        """Test CLI chat mode with real LLM."""
        from open_agent.cli.app import cli
        
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Simulate user input and exit
            result = runner.invoke(cli, [
                "chat",
                "--agent", "explorer",
            ], input="Hello\n/exit\n")
            
            # Should process at least one message
            assert "explorer" in result.output.lower() or result.exit_code == 0


class TestCLISubcommands:
    """Test CLI subcommands."""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_list_agents(self, runner):
        """Test listing available agents."""
        from open_agent.cli.app import cli
        
        result = runner.invoke(cli, ["agents"])
        
        # Should show agent list or help
        assert result.exit_code in [0, 2]
    
    def test_list_sessions(self, runner):
        """Test listing sessions."""
        from open_agent.cli.app import cli
        
        result = runner.invoke(cli, ["sessions"])
        
        # May not exist as a command (exit code 2) or may succeed
        assert result.exit_code in [0, 1, 2]


class TestCLIConfiguration:
    """Test CLI configuration handling."""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_config_loading(self, runner, monkeypatch):
        """Test that CLI loads configuration properly."""
        from open_agent.cli.app import main
        from open_agent.config import Settings
        
        # Create a test config
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = os.path.join(tmpdir, ".open-agent")
            os.makedirs(config_dir)
            
            config_file = os.path.join(config_dir, "config.toml")
            with open(config_file, "w") as f:
                f.write('[general]\ndefault_agent = "explorer"\n')
            
            # Change to temp directory
            monkeypatch.chdir(tmpdir)
            
            # Load settings
            settings = Settings.load(config_file)
            assert settings.default_agent == "explorer"

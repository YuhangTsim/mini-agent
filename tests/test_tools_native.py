"""Tests for native tools (file operations, search, command execution)."""

from __future__ import annotations

import os
import tempfile

import pytest

from open_agent.tools.base import ToolContext, ToolResult
from open_agent.tools.native.file_ops import ReadFileTool, WriteFileTool, EditFileTool
from open_agent.tools.native.search import SearchFilesTool, ListFilesTool
from open_agent.tools.native.command import ExecuteCommandTool


@pytest.fixture
def tool_context():
    """Create a tool context for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield ToolContext(
            session_id="test-session-1",
            working_directory=tmpdir,
        )


class TestReadFileTool:
    """Test read_file tool."""
    
    @pytest.fixture
    def tool(self):
        return ReadFileTool()
    
    async def test_read_existing_file(self, tool, tool_context):
        """Test reading an existing file."""
        # Create a test file
        test_file = os.path.join(tool_context.working_directory, "test.txt")
        with open(test_file, "w") as f:
            f.write("Hello, World!")
        
        result = await tool.execute({"path": "test.txt"}, tool_context)
        
        assert isinstance(result, ToolResult)
        assert not result.is_error
        assert "Hello, World!" in result.output
    
    async def test_read_nonexistent_file(self, tool, tool_context):
        """Test reading a file that doesn't exist."""
        result = await tool.execute({"path": "nonexistent.txt"}, tool_context)
        
        assert isinstance(result, ToolResult)
        assert result.is_error
    
    async def test_read_with_offset_and_limit(self, tool, tool_context):
        """Test reading with offset and limit."""
        test_file = os.path.join(tool_context.working_directory, "lines.txt")
        with open(test_file, "w") as f:
            for i in range(10):
                f.write(f"Line {i}\n")
        
        result = await tool.execute(
            {"path": "lines.txt", "offset": 2, "limit": 3},
            tool_context
        )
        
        assert not result.is_error
    
    def test_tool_metadata(self, tool):
        """Test tool metadata."""
        assert tool.name == "read_file"
        assert tool.description is not None


class TestWriteFileTool:
    """Test write_file tool."""
    
    @pytest.fixture
    def tool(self):
        return WriteFileTool()
    
    async def test_write_new_file(self, tool, tool_context):
        """Test writing a new file."""
        result = await tool.execute(
            {"path": "newfile.txt", "content": "New content"},
            tool_context
        )
        
        assert isinstance(result, ToolResult)
        assert not result.is_error
        
        # Verify file was created
        full_path = os.path.join(tool_context.working_directory, "newfile.txt")
        assert os.path.exists(full_path)
        with open(full_path) as f:
            assert f.read() == "New content"
    
    async def test_overwrite_existing_file(self, tool, tool_context):
        """Test overwriting an existing file."""
        # Create initial file
        test_file = os.path.join(tool_context.working_directory, "overwrite.txt")
        with open(test_file, "w") as f:
            f.write("Original")
        
        result = await tool.execute(
            {"path": "overwrite.txt", "content": "Updated"},
            tool_context
        )
        
        assert not result.is_error
        with open(test_file) as f:
            assert f.read() == "Updated"
    
    async def test_create_nested_directories(self, tool, tool_context):
        """Test creating nested directories."""
        result = await tool.execute(
            {"path": "nested/dir/file.txt", "content": "Deep content"},
            tool_context
        )
        
        assert not result.is_error
        full_path = os.path.join(tool_context.working_directory, "nested/dir/file.txt")
        assert os.path.exists(full_path)
    
    async def test_write_empty_content(self, tool, tool_context):
        """Test writing empty content."""
        result = await tool.execute(
            {"path": "empty.txt", "content": ""},
            tool_context
        )
        
        assert not result.is_error
        full_path = os.path.join(tool_context.working_directory, "empty.txt")
        assert os.path.exists(full_path)
    
    def test_tool_metadata(self, tool):
        """Test tool metadata."""
        assert tool.name == "write_file"
        assert tool.description is not None


class TestEditFileTool:
    """Test edit_file tool."""
    
    @pytest.fixture
    def tool(self):
        return EditFileTool()
    
    async def test_replace_text(self, tool, tool_context):
        """Test replacing text in a file."""
        test_file = os.path.join(tool_context.working_directory, "edit.txt")
        with open(test_file, "w") as f:
            f.write("Hello OLD World")
        
        result = await tool.execute(
            {
                "path": "edit.txt",
                "old_string": "OLD",
                "new_string": "NEW",
            },
            tool_context
        )
        
        assert not result.is_error
        with open(test_file) as f:
            content = f.read()
        assert "Hello NEW World" in content
    
    async def test_invalid_old_string(self, tool, tool_context):
        """Test with old_string that doesn't exist."""
        test_file = os.path.join(tool_context.working_directory, "no_match.txt")
        with open(test_file, "w") as f:
            f.write("Some content")
        
        result = await tool.execute(
            {
                "path": "no_match.txt",
                "old_string": "NONEXISTENT",
                "new_string": "replacement",
            },
            tool_context
        )
        
        assert result.is_error
    
    async def test_edit_nonexistent_file(self, tool, tool_context):
        """Test editing a file that doesn't exist."""
        result = await tool.execute(
            {
                "path": "nonexistent.txt",
                "old_string": "old",
                "new_string": "new",
            },
            tool_context
        )
        
        assert result.is_error
    
    def test_tool_metadata(self, tool):
        """Test tool metadata."""
        assert tool.name == "edit_file"
        assert tool.description is not None


class TestSearchFilesTool:
    """Test search_files tool."""
    
    @pytest.fixture
    def tool(self):
        return SearchFilesTool()
    
    async def test_search_with_pattern(self, tool, tool_context):
        """Test searching with a pattern."""
        # Create test files
        with open(os.path.join(tool_context.working_directory, "a.py"), "w") as f:
            f.write("def hello(): pass")
        with open(os.path.join(tool_context.working_directory, "b.py"), "w") as f:
            f.write("def world(): pass")
        
        result = await tool.execute(
            {"pattern": "def ", "path": "."},
            tool_context
        )
        
        assert not result.is_error
    
    async def test_search_no_matches(self, tool, tool_context):
        """Test searching with no matches."""
        result = await tool.execute(
            {"pattern": "xyz123nonexistent", "path": "."},
            tool_context
        )
        
        assert not result.is_error
    
    def test_tool_metadata(self, tool):
        """Test tool metadata."""
        assert tool.name == "search_files"
        assert tool.description is not None


class TestListFilesTool:
    """Test list_files tool."""
    
    @pytest.fixture
    def tool(self):
        return ListFilesTool()
    
    async def test_list_directory(self, tool, tool_context):
        """Test listing directory contents."""
        # Create some files
        open(os.path.join(tool_context.working_directory, "file1.txt"), "w").close()
        open(os.path.join(tool_context.working_directory, "file2.py"), "w").close()
        os.makedirs(os.path.join(tool_context.working_directory, "subdir"))
        
        result = await tool.execute({"path": "."}, tool_context)
        
        assert not result.is_error
    
    def test_tool_metadata(self, tool):
        """Test tool metadata."""
        assert tool.name == "list_files"
        assert tool.description is not None


class TestExecuteCommandTool:
    """Test execute_command tool."""
    
    @pytest.fixture
    def tool(self):
        return ExecuteCommandTool()
    
    async def test_execute_valid_command(self, tool, tool_context):
        """Test executing a valid command."""
        result = await tool.execute(
            {"command": "echo 'Hello World'"},
            tool_context
        )
        
        assert isinstance(result, ToolResult)
        assert not result.is_error
        assert "Hello World" in result.output
    
    async def test_execute_invalid_command(self, tool, tool_context):
        """Test executing an invalid command."""
        result = await tool.execute(
            {"command": "nonexistent_command_xyz"},
            tool_context
        )
        
        assert result.is_error
    
    def test_tool_metadata(self, tool):
        """Test tool metadata."""
        assert tool.name == "execute_command"
        assert tool.description is not None

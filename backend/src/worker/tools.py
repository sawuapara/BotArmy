"""Tool definitions (JSON schemas for the LLM) and executor."""

import asyncio
import logging
import os
from pathlib import Path

import httpx

logger = logging.getLogger("jarvis.worker.tools")


def safe_resolve(worktree_path: str, relative_path: str) -> Path:
    """Resolve a path relative to worktree, preventing path traversal."""
    base = Path(worktree_path).resolve()
    target = (base / relative_path).resolve()
    if not str(target).startswith(str(base)):
        raise ValueError(f"Path traversal blocked: {relative_path}")
    return target


TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "read_file",
        "description": "Read the contents of a file at the given path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file to read.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file at the given path, creating parent directories as needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file to write.",
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file.",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_files",
        "description": "List files and directories at the given path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the directory to list. Defaults to '.' (root).",
                    "default": ".",
                },
            },
        },
    },
    {
        "name": "run_command",
        "description": "Run a shell command in the working directory. Returns stdout and stderr.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute.",
                },
            },
            "required": ["command"],
        },
    },
]


async def execute_tool(name: str, input: dict, worktree_path: str) -> str:
    """Execute a tool and return the string result."""
    try:
        if name == "read_file":
            path = safe_resolve(worktree_path, input["path"])
            if not path.exists():
                return f"Error: File not found: {input['path']}"
            return path.read_text()

        elif name == "write_file":
            path = safe_resolve(worktree_path, input["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(input["content"])
            return f"File written successfully: {input['path']}"

        elif name == "list_files":
            rel = input.get("path", ".")
            path = safe_resolve(worktree_path, rel)
            if not path.exists():
                return f"Error: Directory not found: {rel}"
            entries = sorted(os.listdir(path))
            return "\n".join(entries) if entries else "(empty directory)"

        elif name == "run_command":
            proc = await asyncio.create_subprocess_shell(
                input["command"],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=worktree_path,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            except asyncio.TimeoutError:
                proc.kill()
                return "Error: Command timed out after 60 seconds."

            result = ""
            if stdout:
                result += stdout.decode(errors="replace")
            if stderr:
                result += "\nSTDERR:\n" + stderr.decode(errors="replace")
            if proc.returncode != 0:
                result += f"\n(exit code: {proc.returncode})"
            return result.strip() or "(no output)"

        else:
            return f"Error: Unknown tool '{name}'"

    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        logger.exception("Tool execution error: %s", name)
        return f"Error executing {name}: {e}"


# --- Task-creator tools ---

TASK_CREATOR_TOOLS: list[dict] = [
    {
        "name": "create_task",
        "description": "Create a new task in Jarvis. Call this when you have gathered enough information from the user to define the task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Clear, concise task title"},
                "description": {
                    "type": "string",
                    "description": "Detailed description of what needs to be done",
                },
                "priority": {
                    "type": "integer",
                    "description": "Priority 0-100 (50=normal, 75+=high, 25-=low)",
                    "default": 50,
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags for categorization",
                    "default": [],
                },
                "project": {
                    "type": "string",
                    "description": "Project identifier if mentioned",
                },
                "estimated_hours": {
                    "type": "number",
                    "description": "Estimated hours if discussed",
                },
            },
            "required": ["title", "description"],
        },
    },
]


async def execute_task_creator_tool(name: str, input: dict, api_base: str) -> str:
    """Execute a task-creator tool by calling the backend API."""
    if name == "create_task":
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                res = await client.post(f"{api_base}/tasks", json=input)
                if res.status_code == 200:
                    task = res.json()
                    return (
                        f"Task created successfully: '{task['title']}' "
                        f"(ID: {task['id']}, priority: {task['priority']})"
                    )
                else:
                    return f"Error creating task: {res.status_code} {res.text}"
        except Exception as e:
            logger.exception("Task creation failed")
            return f"Error creating task: {e}"
    return f"Unknown tool: {name}"

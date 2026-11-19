"""Map each tool's hook JSON (stdin) to the normalised /v1/check event.

The normalised event is:

    { "event": "prompt" | "tool" | "diff",
      "text":  str,     # prompt text, or a tool command (Bash)
      "diff":  str,     # new file content for Write/Edit (secret scan + Stage A)
      "path":  str,     # file path for Write/Edit
      "tool":  str,     # the coding tool: "claude-code" | "kiro"
      "tool_call": str, # the underlying tool/command name (Write/Edit/Bash/...)
      "repo":  str,
      "user":  str }

Write/Edit tool calls are sent as a ``diff``-type event carrying the NEW file
content (so the deterministic secret scan and the artefact stage see it) plus
the path. Bash is sent as a ``tool`` event with the command in ``text``.

Claude Code hook JSON follows https://code.claude.com/docs/en/hooks :
  UserPromptSubmit -> {"hook_event_name","prompt","cwd",...}
  PreToolUse       -> {"hook_event_name","tool_name","tool_input":{...},"cwd",...}
                      Write/Edit tool_input: {"file_path","content"|"new_string"}
                      Bash tool_input:       {"command"}

Kiro hook JSON (https://kiro.dev/docs/hooks/ , /docs/hooks/types , /actions):
  UserPromptSubmit -> the prompt text is in the USER_PROMPT environment variable
                      (per the docs); session context (incl. cwd) is on stdin.
  PreToolUse       -> {"hook_event_name":"PreToolUse","cwd","session_id",
                       "tool_name","tool_input":{...}} on stdin. MCP tools use
                      the sanitized id mcp_<server>_<tool>.
The prompt mapper prefers USER_PROMPT and falls back to stdin keys; the tool
mapper reads tool_name/tool_input defensively across a few key spellings.
Documented in docs/v2/PHASE-2.md.
"""

from __future__ import annotations

import os
from typing import Any

# Tool-call names whose file content we treat as a diff-type write.
_WRITE_TOOLS = {"write", "edit", "multiedit", "create", "fsappend", "fswrite", "strreplace"}
_SHELL_TOOLS = {"bash", "shell", "executebash", "run", "command"}


def _first(d: dict, keys: list[str], default: Any = "") -> Any:
    for k in keys:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return default


def _repo_user(raw: dict) -> tuple[str, str]:
    repo = _first(raw, ["repo", "repository", "cwd", "workspacePath", "workspace_root", "projectRoot"], "")
    user = _first(raw, ["user", "actor", "userId", "user_id"], "")
    return str(repo), str(user)


def map_claude(event: str, raw: dict) -> dict:
    """Map Claude Code hook JSON to the normalised event."""
    repo, user = _repo_user(raw)
    base = {"tool": "claude-code", "repo": repo, "user": user, "tool_call": ""}

    if event == "prompt":
        base.update(event="prompt", text=str(_first(raw, ["prompt", "user_prompt", "text"], "")))
        return base

    # tool event
    tool_name = str(_first(raw, ["tool_name", "toolName", "name"], ""))
    tool_input = _first(raw, ["tool_input", "toolInput", "input", "arguments"], {}) or {}
    base["tool_call"] = tool_name
    low = tool_name.lower()

    if low in _WRITE_TOOLS:
        content = _first(tool_input, ["content", "new_string", "newStr", "text", "new_content"], "")
        path = _first(tool_input, ["file_path", "path", "filePath", "target_file", "targetFile"], "")
        base.update(event="diff", text="", diff=str(content), path=str(path))
        return base
    if low in _SHELL_TOOLS:
        command = _first(tool_input, ["command", "cmd", "script"], "")
        base.update(event="tool", text=str(command))
        return base

    # Other tool (incl. mcp__*): classify on its text-ish argument, no file.
    base.update(event="tool", text=str(_first(tool_input, ["command", "text", "query", "prompt"], "")))
    return base


# Kiro key guesses (defensive — see module docstring and PHASE-2.md).
KIRO_PROMPT_KEYS = ["prompt", "promptText", "userInput", "user_input", "text", "message"]
KIRO_TOOL_NAME_KEys = ["toolName", "tool_name", "tool", "name"]
KIRO_TOOL_INPUT_KEYS = ["toolInput", "tool_input", "input", "arguments", "args"]


def map_kiro(event: str, raw: dict) -> dict:
    """Map Kiro hook JSON to the normalised event (defensive field reading)."""
    repo, user = _repo_user(raw)
    base = {"tool": "kiro", "repo": repo, "user": user, "tool_call": ""}

    if event == "prompt":
        # Per the Kiro docs the prompt text is in the USER_PROMPT env var;
        # fall back to stdin keys for other surfaces/versions.
        text = os.environ.get("USER_PROMPT") or str(_first(raw, KIRO_PROMPT_KEYS, ""))
        base.update(event="prompt", text=text)
        return base

    tool_name = str(_first(raw, KIRO_TOOL_NAME_KEys, ""))
    tool_input = _first(raw, KIRO_TOOL_INPUT_KEYS, {}) or {}
    if not isinstance(tool_input, dict):
        tool_input = {"text": str(tool_input)}
    base["tool_call"] = tool_name
    low = tool_name.lower()

    if low in _WRITE_TOOLS:
        content = _first(tool_input, ["content", "new_string", "newStr", "text", "fileText", "contents"], "")
        path = _first(tool_input, ["path", "file_path", "filePath", "target_file"], "")
        base.update(event="diff", text="", diff=str(content), path=str(path))
        return base
    if low in _SHELL_TOOLS:
        command = _first(tool_input, ["command", "cmd", "script"], "")
        base.update(event="tool", text=str(command))
        return base

    base.update(event="tool", text=str(_first(tool_input, ["command", "text", "query", "prompt"], "")))
    return base


_MAPPERS = {"claude": map_claude, "kiro": map_kiro}


def map_event(tool: str, event: str, raw: dict) -> dict:
    mapper = _MAPPERS.get(tool)
    if mapper is None:
        raise ValueError(f"unknown tool {tool!r}; expected one of {sorted(_MAPPERS)}")
    if event not in ("prompt", "tool"):
        raise ValueError(f"unknown event {event!r}; expected 'prompt' or 'tool'")
    return mapper(event, raw)

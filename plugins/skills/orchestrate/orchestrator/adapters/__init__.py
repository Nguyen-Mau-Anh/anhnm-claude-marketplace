"""Adapters for external system integration."""

from .claude_spawner import ClaudeSpawner, TaskResult

__all__ = ["ClaudeSpawner", "TaskResult"]

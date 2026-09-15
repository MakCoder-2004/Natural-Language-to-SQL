"""Construction of the bounded controlled agent tool interface."""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.tools import StructuredTool

from app.agent.tools import BoundedToolSet


@dataclass(frozen=True, slots=True)
class ControlledAgent:
    """A non-autonomous agent facade with an explicit fixed tool allowlist."""

    tool_set: BoundedToolSet

    @property
    def tools(self) -> tuple[StructuredTool, ...]:
        """Return the only tools available to a model invocation."""

        return self.tool_set.langchain_tools()

    @property
    def tool_names(self) -> frozenset[str]:
        """Return names for safe inspection and telemetry."""

        return frozenset(tool.name for tool in self.tools)

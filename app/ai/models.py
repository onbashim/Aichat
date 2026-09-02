from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(slots=True)
class AIMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(slots=True)
class AIResult:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

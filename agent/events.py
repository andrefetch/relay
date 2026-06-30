from enum import Enum
from dataclasses import dataclass

class AgentEventType(str, Enum):

    # Agentic lifestyle & loop
    AGENT_START="agent_start"
    AGENT_END="agent_end"
    AGENT_ERROR="agent_error"

    # Text streaming
    TEXT_DELTA = "text_delta"
    TEXT_COMPLETE = "text_complete"

class AgentEvent:
    type: AgentEventType
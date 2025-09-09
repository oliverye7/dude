from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from datetime import datetime


class ActionType(Enum):
    USER_INPUT = "USER_INPUT"
    PROCESS_USER_INPUT = "PROCESS_USER_INPUT"
    AGENT_PLANNING = "AGENT_PLANNING"
    AGENT_TOOL_SEARCH = "AGENT_TOOL_SEARCH"
    PROCESS_AGENT_TOOL_SEARCH_RESULT = "PROCESS_AGENT_TOOL_SEARCH_RESULT"
    AGENT_TOOL_EXECUTION = "AGENT_TOOL_EXECUTION"
    PROCESS_AGENT_TOOL_EXECUTION_RESULT = "PROCESS_AGENT_TOOL_EXECUTION_RESULT"
    AGENT_RESPONSE = "AGENT_RESPONSE"
    AWAIT_USER_INPUT = "AWAIT_USER_INPUT"
    DEFAULT = "DEFAULT"


@dataclass
class Action:
    """Represents a single action taken in a conversation"""
    id: str
    action_type: ActionType
    timestamp: datetime
    content: str  # The action content (reasoning, tool call, etc)
    tool_name: Optional[str] = None  # Set if this is a tool call
    tool_args: Optional[Dict[str, Any]] = None
    tool_result: Optional[Any] = None
    metadata: Optional[Dict[str, Any]] = None
    action_parameters: Optional[Dict[str, Any]] = None
    tool_search_query: Optional[str] = None  # Query used for tool search


@dataclass
class ActionNode:
    """ Represents a node in the action DAG """
    action: Action
    parent_id: Optional[str] = None
    node_id: Optional[uuid.UUID] = None
    children_ids: Optional[List[str]] = None

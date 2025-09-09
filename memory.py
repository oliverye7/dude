from dataclasses import asdict
import json
from typing import Dict, List, Optional
from datetime import datetime
import uuid
from models import Action, ActionNode, ActionType


class DAGMemory:
    """DAG based memory generated serially, but allows for branching and backtracking"""

    def __init__(self):
        self.nodes: Dict[uuid.UUID, ActionNode] = {}
        self.current_node_id: Optional[str] = None
        self.root_node_id: Optional[str] = None

    async def add_action(self,
                         content: str, action_type: ActionType = ActionType.DEFAULT,
                         tool_name: str = None, tool_args: dict = None, tool_result=None,
                         metadata: dict = None, action_parameters: dict = None,
                         tool_search_query: str = None,
                         parent_id: Optional[str] = None,
                         ) -> Action:
        """Add an action to memory DAG."""
        if parent_id is None:
            parent_id = self.current_node_id  # default to linear dag

        # Auto-extract tool information based on action type and parameters
        if action_type == ActionType.AGENT_TOOL_SEARCH:
            # For tool search actions, store the search query and results
            if action_parameters:
                tool_search_query = action_parameters.get("tool_search_query")
            tool_result = content  # The search result is the content

        elif action_type == ActionType.AGENT_TOOL_EXECUTION:
            # For tool execution actions, extract tool info from parameters
            if action_parameters:
                tool_name = action_parameters.get("tool_name")
                tool_args = action_parameters.get("tool_args")
            tool_result = content  # The execution result is the content

        action = Action(
            # Simple sequential ID (since actions are generated serially)
            id=str(len(self.nodes)),
            action_type=action_type,
            timestamp=datetime.now(),
            content=content,
            tool_name=tool_name,
            tool_args=tool_args,
            tool_result=tool_result,
            metadata=metadata or {},
            action_parameters=action_parameters or {},
            tool_search_query=tool_search_query
        )

        node = ActionNode(
            action=action,
            parent_id=parent_id,
            children_ids=[],
            node_id=uuid.uuid4()
        )
        self.nodes[node.node_id] = node
        if self.root_node_id is None:
            self.root_node_id = node.node_id

        if parent_id and parent_id in self.nodes:
            self.nodes[parent_id].children_ids.append(node.node_id)

        self.current_node_id = node.node_id
        return action

    def branch(self, node_id: uuid.UUID) -> uuid.UUID:
        """Branch from a node"""
        pass

    def backtrack(self, node_id: uuid.UUID) -> uuid.UUID:
        """
        Backtrack from a node in the action DAG.

        This method is intended to allow the agent to "rewind" its memory to a previous state,
        effectively setting the current node to the specified node_id. This can be useful for
        undoing actions, exploring alternative branches, or recovering from errors.

        """
        pass

    def get_context_between_nodes(self, node_id: uuid.UUID, parent_node_id: uuid.UUID) -> str:
        """Get context between two nodes
        Helpful during backtracking or branching actions
        """
        pass

    def get_context(self) -> str:
        """Get full context as a string"""
        pass

    def clear(self):
        """Clear all memory"""
        self.nodes = {}
        self.current_node_id = None
        self.root_node_id = None


class LinearMemory:
    """Ultra simple linear memory - everything in order"""

    def __init__(self):
        self.actions: List[Action] = []

    async def add_action(self, content: str, action_type: ActionType = ActionType.DEFAULT,
                         tool_name: str = None, tool_args: dict = None, tool_result=None,
                         metadata: dict = None, action_parameters: dict = None,
                         tool_search_query: str = None) -> Action:
        """Add an action to memory"""

        # Auto-extract tool information based on action type and parameters
        if action_type == ActionType.AGENT_TOOL_SEARCH:
            # For tool search actions, store the search query and results
            if action_parameters:
                tool_search_query = action_parameters.get("tool_search_query")
            tool_result = content  # The search result is the content

        elif action_type == ActionType.AGENT_TOOL_EXECUTION:
            # For tool execution actions, extract tool info from parameters
            if action_parameters:
                tool_name = action_parameters.get("tool_name")
                tool_args = action_parameters.get("tool_args")
            tool_result = content  # The execution result is the content

        action = Action(
            id=str(len(self.actions)),  # Simple sequential ID
            action_type=action_type,
            timestamp=datetime.now(),
            content=content,
            tool_name=tool_name,
            tool_args=tool_args,
            tool_result=tool_result,
            metadata=metadata or {},
            action_parameters=action_parameters or {},
            tool_search_query=tool_search_query
        )
        self.actions.append(action)
        return action

    def get_context(self) -> str:
        """Get full context as a string"""
        context_parts = []
        for action in self.actions:
            timestamp = action.timestamp.strftime("%H:%M:%S")

            # Build the main context entry
            action_name = action.action_type.value.replace(
                '_', ' ').upper()
            full_action = json.dumps(asdict(action), indent=2, default=str)
            context_parts.append(
                f"[{timestamp}] {action_name}: \n {full_action}")

        return "\n".join(context_parts)

    def get_recent_context(self, max_actions: int = 10) -> str:
        """Get recent context (most recent actions first)"""
        context_parts = []
        # Get the last max_actions actions, in order from oldest to newest
        recent_actions = self.actions[-max_actions:]
        for action in recent_actions:
            timestamp = action.timestamp.strftime("%H:%M:%S")

            # Build the main context entry
            action_name = action.action_type.value.replace(
                '_', ' ').upper()
            context_parts.append(
                f"[{timestamp}] {action_name}: {action.content}")
            full_action = json.dumps(asdict(action), indent=2, default=str)
            context_parts.append(full_action)

        return "\n".join(context_parts)

    def clear(self):
        """Clear all memory"""
        self.actions = []

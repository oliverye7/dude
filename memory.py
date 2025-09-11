from dataclasses import asdict
import json
from typing import Dict, List, Optional
from datetime import datetime
import uuid
from models import Action, ActionNode, ActionType, NodeMemory, NodeMemoryEntry, NodeMemoryType, TodoMemory, ConversationStateMemory, BranchBacktrackSummaryMemory, ConversationCompressionMemory


class BaseMemory:
    """Base memory class with common functionality"""

    def write_memory_to_file(self) -> str:
        """Write memory to file and return the filename"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"agent_context_{timestamp}.txt"
        context = self.get_context()
        with open(filename, "w", encoding="utf-8") as f:
            f.write(context)
        return filename

    def get_context(self) -> str:
        """Get full context as a string - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement get_context")

    @staticmethod
    def format_action(action: Action) -> str:
        """Helper function to format an action for display"""
        timestamp = action.timestamp.strftime("%H:%M:%S")
        action_name = action.action_type.value.replace('_', ' ').upper()
        full_action = json.dumps(asdict(action), indent=2, default=str)
        return f"[{timestamp}] {action_name}: \n {full_action}"


class DAGMemory(BaseMemory):
    # THIS DAG SHOULD NEVER BE PRUNED
    """DAG based memory generated serially, but allows for branching and backtracking"""

    def __init__(self):
        self.nodes: Dict[uuid.UUID, ActionNode] = {}
        self.current_node_id: Optional[uuid.UUID] = None
        self.root_node_id: Optional[uuid.UUID] = None

    async def add_action(self,
                         content: str, action_type: ActionType = ActionType.DEFAULT,
                         tool_name: str = None, tool_args: dict = None, tool_result=None,
                         metadata: dict = None, action_parameters: dict = None,
                         tool_search_query: str = None,
                         parent_id: Optional[uuid.UUID] = None,
                         node_memory: Optional[NodeMemory] = None
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

        node = None
        if action_type == ActionType.STEP_SUMMARY:
            node = ActionNode(
                action=action,
                parent_id=parent_id,
                children_ids=[],
                node_id=uuid.uuid4(),
                action_node_memory=None,
                step_summary=action.content,
                step_boundary=True
            )
        else:
            node = ActionNode(
                action=action,
                parent_id=parent_id,
                children_ids=[],
                node_id=uuid.uuid4(),
                action_node_memory=NodeMemory(
                    node_memory=[node_memory] if node_memory else []),
                step_boundary=False,
                step_summary=None
            )

        self.nodes[node.node_id] = node
        if self.root_node_id is None:
            self.root_node_id = node.node_id

        # implements branching
        if parent_id and parent_id in self.nodes:
            self.nodes[parent_id].children_ids.append(node.node_id)

        self.current_node_id = node.node_id
        return action

    def get_step_nodes(self) -> List[ActionNode]:
        """Get all step nodes in the action DAG"""
        steps = []
        for node in self.nodes.values():
            if node.step_boundary:
                steps.append(node)
        return steps

    def get_current_action_node(self) -> ActionNode:
        """Get the current action node"""
        if self.current_node_id is None:
            raise ValueError("Current node id is not set")
        return self.nodes[self.current_node_id]

    def get_actions_for_step(self, step_id: uuid.UUID) -> List[ActionNode]:
        """Get all actions for a given step"""
        if step_id not in self.nodes:
            raise ValueError(f"Step {step_id} not found")
        # walk backwards from the step node until previous step boundary or root is reached
        actions = []
        current_node = self.nodes[step_id]
        while current_node:
            actions.append(current_node)
            if current_node.parent_id is None:
                break
            current_node = self.nodes.get(current_node.parent_id)

        actions.reverse()
        return actions

    def update_node(self, node_id: uuid.UUID, action: Action, node_memory: Optional[NodeMemory] = None) -> Action:
        """Update a node in the action DAG"""
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} not found")
        self.nodes[node_id].action = action
        if node_memory:
            self.nodes[node_id].action_node_memory.node_memory.append(
                node_memory)
        return action

    def set_todo_list(self, node_id: uuid.UUID, todo_list: TodoMemory) -> bool:
        """Set the todo list for a given node"""
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} not found")
        current_node_memory = self.nodes[node_id].action_node_memory
        if not current_node_memory:
            raise ValueError(f"Node {node_id} has no action node memory")
        node_memory_entry = NodeMemoryEntry(
            updated_field=NodeMemoryType.TODO,
            timestamp=datetime.now(),
            todo=todo_list,
            conversation_state=current_node_memory.node_memory[-1].conversation_state,
            branch_backtrack_summary=current_node_memory.node_memory[-1].branch_backtrack_summary,
        )
        current_node_memory.node_memory.append(
            node_memory_entry)
        return True

    def set_conversation_compression(self, node_id: uuid.UUID, conversation_compression: ConversationCompressionMemory) -> bool:
        """Set the conversation compression for a given node"""
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} not found")
        current_node_memory = self.nodes[node_id].action_node_memory
        if not current_node_memory:
            raise ValueError(f"Node {node_id} has no action node memory")
        node_memory_entry = NodeMemoryEntry(
            updated_field=NodeMemoryType.CONVERSATION_COMPRESSION,
            timestamp=datetime.now(),
            conversation_compression=conversation_compression,
            todo=current_node_memory.node_memory[-1].todo,
            conversation_state=current_node_memory.node_memory[-1].conversation_state,
            branch_backtrack_summary=current_node_memory.node_memory[-1].branch_backtrack_summary,
        )
        current_node_memory.node_memory.append(
            node_memory_entry)
        return True

    def set_conversation_state(self, node_id: uuid.UUID, conversation_state: ConversationStateMemory) -> bool:
        """Set the conversation state for a given node"""
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} not found")
        current_node_memory = self.nodes[node_id].action_node_memory
        if not current_node_memory:
            raise ValueError(f"Node {node_id} has no action node memory")
        node_memory_entry = NodeMemoryEntry(
            updated_field=NodeMemoryType.CONVERSATION_STATE,
            timestamp=datetime.now(),
            conversation_state=conversation_state,
            todo=current_node_memory.node_memory[-1].todo,
            branch_backtrack_summary=current_node_memory.node_memory[-1].branch_backtrack_summary,
        )
        current_node_memory.node_memory.append(
            node_memory_entry)
        return True

    def get_node_memory_history_for_node(self, node_id: uuid.UUID) -> List[NodeMemory]:
        """Get the node memory history for a given node"""
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} not found")
        action_node_memory = self.nodes[node_id].action_node_memory
        if not action_node_memory:
            raise ValueError(f"Node {node_id} has no action node memory")
        return action_node_memory

    def get_todo_list(self, node_id: Optional[uuid.UUID] = None) -> Optional[TodoMemory]:
        """Get the todo list for a given node"""
        if node_id is None:
            node_id = self.current_node_id
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} not found")
        action_node_memory = self.nodes[node_id].action_node_memory
        if not action_node_memory:
            raise ValueError(f"Node {node_id} has no action node memory")
        return action_node_memory.node_memory[-1].todo if action_node_memory.node_memory[-1].todo else None

    def get_conversation_state(self, node_id: Optional[uuid.UUID] = None) -> Optional[ConversationStateMemory]:
        """Get the conversation state for a given node"""
        if node_id is None:
            node_id = self.current_node_id
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} not found")
        action_node_memory = self.nodes[node_id].action_node_memory
        return action_node_memory.node_memory[-1].conversation_state if action_node_memory.node_memory[-1].conversation_state else None

    def get_branch_backtrack_summary(self, node_id: Optional[uuid.UUID] = None) -> Optional[BranchBacktrackSummaryMemory]:
        """Get the branch backtrack summary for a given node"""
        if node_id is None:
            node_id = self.current_node_id
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} not found")
        action_node_memory = self.nodes[node_id].action_node_memory
        return action_node_memory.node_memory[-1].branch_backtrack_summary if action_node_memory.node_memory[-1].branch_backtrack_summary else None

    def get_current_node_memory(self, node_id: Optional[uuid.UUID] = None) -> Optional[NodeMemory]:
        """Get the current node memory for a given node"""
        if node_id is None:
            node_id = self.current_node_id
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} not found")
        action_node_memory = self.nodes[node_id].action_node_memory
        return action_node_memory.node_memory[-1] if action_node_memory.node_memory[-1] else None

    def get_node_by_id(self, node_id: uuid.UUID) -> ActionNode:
        """Get a node by its ID"""
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} not found")
        return self.nodes[node_id]

    def get_path_to_root(self, node_id: uuid.UUID) -> List[uuid.UUID]:
        """Get the path to the root node from a given node"""
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} not found")
        path = []
        current_node = self.nodes[node_id]
        while current_node.parent_id:
            path.append(current_node.parent_id)
            current_node = self.nodes[current_node.parent_id]
        return path

    def get_all_branch_node_ids(self) -> List[uuid.UUID]:
        """Get all branches in the action DAG"""
        branches = []
        for node in self.nodes.values():
            if len(node.children_ids) > 1:
                branches.append(node.node_id)
        return branches

    def get_all_leaf_node_ids(self) -> List[uuid.UUID]:
        """Get all leaf nodes in the action DAG"""
        leaves = []
        for node in self.nodes.values():
            if len(node.children_ids) == 0:
                leaves.append(node.node_id)
        return leaves

    # effectively git checkout
    def set_current_node(self, node_id: uuid.UUID) -> uuid.UUID:
        """Set the current node"""
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} not found")
        self.current_node_id = node_id
        return node_id

    def backtrack(self, node_id: uuid.UUID, notes: str) -> uuid.UUID:
        """
        Backtrack from a node in the action DAG.

        This method is intended to allow the agent to "rewind" its memory to a previous state,
        effectively setting the current node to the specified node_id. This can be useful for
        undoing actions, exploring alternative branches, or recovering from errors.

        """
        if node_id not in self.nodes:
            raise ValueError(f"Node {node_id} not found")

        if not notes:
            raise ValueError("Notes are required!")

        action = self.nodes[node_id].action
        action.metadata["notes"] = notes
        self.update_node(node_id, action)
        self.set_current_node(node_id)
        return node_id

    def get_context_between_nodes(self, starting_node_id: uuid.UUID, ending_node_id: uuid.UUID) -> str:
        """
        Get context between two nodes
        Helpful during backtracking or branching actions
        Assumes nodes are connected and are part of the same branch
        """
        if starting_node_id not in self.nodes or ending_node_id not in self.nodes:
            raise ValueError("Nodes not found")
        context = []
        current_node = self.nodes[starting_node_id]
        visited = set()

        while current_node.node_id != ending_node_id:
            if current_node.node_id in visited:
                raise ValueError(f"Cycle detected in DAG traversal")
            visited.add(current_node.node_id)
            context.append(current_node.action)

            if current_node.parent_id is None:
                raise ValueError(
                    f"Node {ending_node_id} is not reachable from {starting_node_id}")
            if current_node.parent_id not in self.nodes:
                raise ValueError(
                    f"Parent node {current_node.parent_id} not found")

            current_node = self.nodes[current_node.parent_id]
        context.append(current_node.action)
        return "\n".join([self.format_action(action) for action in reversed(context)])

    def get_current_context(self) -> str:
        """Get context of the current node"""
        if self.current_node_id is None:
            return ""
        if self.root_node_id is None:
            return ""
        return self.get_context_between_nodes(self.current_node_id, self.root_node_id)

    def get_context(self) -> str:
        """Get full context as a string"""
        return self.get_current_context()

    def get_recent_context(self, max_actions: int = 10) -> str:
        """Get recent context (most recent actions first)"""
        if self.current_node_id is None:
            return ""
        if self.root_node_id is None:
            return ""
        recent_root_node_id = self.get_path_to_root(
            self.current_node_id)[-max_actions]
        return self.get_context_between_nodes(self.current_node_id, recent_root_node_id)

    def get_conversation_length(self) -> int:
        """Get the length of the conversation"""
        if self.current_node_id is None:
            return 0
        if self.root_node_id is None:
            return 0
        # since actions are added sequentially, this is the length of the conversation
        return self.get_node_by_id(self.current_node_id).action.id

    def get_branch_length(self) -> int:
        """Get the length of the branch"""
        if self.current_node_id is None:
            return 0
        if self.root_node_id is None:
            return 0
        return len(self.get_path_to_root(self.current_node_id))

    def get_step_count(self) -> int:
        """Get the number of steps in the conversation"""
        return len(self.get_step_nodes())

    def clear(self):
        """Clear all memory"""
        self.nodes = {}
        self.current_node_id = None
        self.root_node_id = None


class LinearMemory(BaseMemory):
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
        return "\n".join([self.format_action(action) for action in self.actions])

    def get_recent_context(self, max_actions: int = 10) -> str:
        """Get recent context (most recent actions first)"""
        recent_actions = self.actions[-max_actions:]
        return "\n".join([self.format_action(action) for action in recent_actions])

    def clear(self):
        """Clear all memory"""
        self.actions = []

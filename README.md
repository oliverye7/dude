# Dude

A lightweight Python agent runtime for building conversational AI agents with tool integration.

## What's Included

- **Agent**: Core agent runtime with tool execution and an action state machine
- **Memory**: 
    - Linear memory implementation for conversation history
    - DAG based memory implementation for backtracking and conversation branching
- **Models**: Action and ActionType data structures for agent state tracking
- **Gateway Tools**: MCP (Model Context Protocol) integration for tool connectivity
- **LLM Provider**: Gemini API integration for language model interactions

## Key Components

- Tool discovery and execution through MCP gateway
- Conversation memory management
- Action-based state tracking and DAG representation
- Async/await support for concurrent operations

## Quick Start

1) make a pyenv
2) run the gateway (setup here: https://github.com/oliverye7/mcp-gateway)
3) run the agent (`python3 agent.py`)

from typing import Dict, Any, List, Optional, Tuple
import json
import asyncio
from dotenv import load_dotenv
from memory import LinearMemory, DAGMemory
from models import Action, ActionType
from llm import GeminiProvider
from gateway_tools import MCPGatewayTools

# Load environment variables from .env file
load_dotenv()


class Agent:
    """Lightweight linear agent runtime"""
    MAX_ACTIONS = 10
    ACTION_MAX_RETRIES = 3

    def __init__(self, tools: Dict[str, Any] = None):
        self.memory = DAGMemory()
        self.llm = GeminiProvider()
        self.gateway_tools = MCPGatewayTools()
        self.session_id = None

    async def execute_tool():
        pass

    async def get_relevant_tools():
        pass

    async def think():
        pass

    async def get_context(self):
        return self.memory.get_context()

    async def should_stop():
        pass

    async def clear_memory():
        pass

    def get_prompt(self, action_type: ActionType):
        if action_type == ActionType.PROCESS_USER_INPUT:
            with open('prompts/process_user_input_prompt.md', 'r') as f:
                return f.read()
        elif action_type == ActionType.AGENT_RESPONSE:
            with open('prompts/agent_response_prompt.md', 'r') as f:
                return f.read()
        elif action_type == ActionType.AGENT_PLANNING:
            with open('prompts/agent_planning_prompt.md', 'r') as f:
                return f.read()
        elif action_type == ActionType.PROCESS_AGENT_TOOL_SEARCH_RESULT:
            with open('prompts/process_tool_search_result_prompt.md', 'r') as f:
                return f.read()
        elif action_type == ActionType.PROCESS_AGENT_TOOL_EXECUTION_RESULT:
            with open('prompts/process_tool_execution_result_prompt.md', 'r') as f:
                return f.read()
        elif action_type == ActionType.STEP_SUMMARY:
            with open('prompts/step_summary_prompt.md', 'r') as f:
                return f.read()
        else:
            raise ValueError(
                f"No prompt available for action type: {action_type}")

    def parse_response(self, response: str, action_type: ActionType) -> Tuple[str, ActionType, Optional[Dict[Any, Any]]]:
        # parse the JSON response for the next action
        try:
            # Strip markdown code blocks if present
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]  # Remove ```json
            if cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:]  # Remove ```
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]  # Remove trailing ```
            cleaned_response = cleaned_response.strip()

            response_data = json.loads(cleaned_response)
            response_text = response_data.get("response")
            if not response_text:
                raise ValueError(
                    f"Response does not contain 'response' field: {response}")

            # For AGENT_RESPONSE action type, don't expect a next_action field
            if action_type == ActionType.AGENT_RESPONSE:
                return response_text, ActionType.AWAIT_USER_INPUT, None

            next_action = response_data.get("next_action")
            if not next_action:
                raise ValueError(
                    f"Response does not contain 'next_action' field: {response}")

            if next_action == "AGENT_TOOL_SEARCH":
                next_action_parameters = response_data.get(
                    "next_action_parameters")
                if not next_action_parameters:
                    raise ValueError(
                        f"Response does not contain 'next_action_parameters' field: {response}")
                assert isinstance(
                    next_action_parameters, dict), f"next_action_parameters is not a dict: {next_action_parameters}. It is a {type(next_action_parameters)}"
                return response_text, ActionType(next_action), next_action_parameters

            # For all other actions, return None for parameters
            next_action_parameters = response_data.get(
                "next_action_parameters")
            return response_text, ActionType(next_action), next_action_parameters
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Response is not valid JSON: {response}. Error: {e}")
        except KeyError as e:
            raise ValueError(f"Response JSON missing required field: {e}")
        except ValueError as e:
            if "is not a valid ActionType" in str(e):
                raise ValueError(
                    f"Invalid action type in response: {next_action}")
            raise

    async def run_process_user_input_action(self, user_input: str, context: str, available_next_actions: List[ActionType]) -> Tuple[str, ActionType, Optional[Dict[Any, Any]]]:
        prompt = self.get_prompt(ActionType.PROCESS_USER_INPUT)

        joined_context = context + "\n\n" + "USER: " + user_input

        response = await self.llm.generate(joined_context, prompt)
        response_text, proposed_next_action, next_action_parameters = self.parse_response(
            response, ActionType.PROCESS_USER_INPUT)

        retries = 0
        # to prevent LLM hallucinations just do a retry
        while proposed_next_action not in available_next_actions and retries < self.ACTION_MAX_RETRIES:
            retries += 1
            response = await self.llm.generate(joined_context, prompt)
            response_text, proposed_next_action, next_action_parameters = self.parse_response(
                response, ActionType.PROCESS_USER_INPUT)

        if retries == self.ACTION_MAX_RETRIES:
            raise ValueError(
                f"Failed to get a valid next action after {self.ACTION_MAX_RETRIES} retries")

        return response_text, proposed_next_action, next_action_parameters

    async def run_agent_planning_action(self, context: str, available_next_actions: List[ActionType]) -> Tuple[str, ActionType, Optional[Dict[Any, Any]]]:
        prompt = self.get_prompt(ActionType.AGENT_PLANNING)

        response = await self.llm.generate(context, prompt)
        response_text, proposed_next_action, next_action_parameters = self.parse_response(
            response, ActionType.AGENT_PLANNING)

        retries = 0
        # to prevent LLM hallucinations just do a retry
        while proposed_next_action not in available_next_actions and retries < self.ACTION_MAX_RETRIES:
            retries += 1
            response = await self.llm.generate(context, prompt)
            response_text, proposed_next_action, next_action_parameters = self.parse_response(
                response, ActionType.AGENT_PLANNING)

        if retries == self.ACTION_MAX_RETRIES:
            raise ValueError(
                f"Failed to get a valid next action after {self.ACTION_MAX_RETRIES} retries")

        return response_text, proposed_next_action, next_action_parameters

    async def run_agent_tool_search_action(self, action_parameters: Optional[Dict[Any, Any]] = None) -> Tuple[str, ActionType, Optional[Dict[Any, Any]]]:
        if not self.gateway_tools.session_id:
            await self.gateway_tools.create_session()

        assert action_parameters is not None, "action_parameters is required for AGENT_TOOL_SEARCH"
        assert isinstance(
            action_parameters, dict), f"action_parameters is not a dict: {action_parameters}. It is a {type(action_parameters)}"
        assert "tool_search_query" in action_parameters, "tool_search_query is required for AGENT_TOOL_SEARCH"
        tool_search_query = action_parameters["tool_search_query"]

        search_result = await self.gateway_tools.search_tools(tool_search_query)

        # Return the action_parameters so we can capture search query in memory
        return search_result, ActionType.PROCESS_AGENT_TOOL_SEARCH_RESULT, action_parameters

    async def run_process_agent_tool_search_result_action(self, context: str, available_next_actions: List[ActionType]) -> Tuple[str, ActionType, Optional[Dict[Any, Any]]]:
        prompt = self.get_prompt(ActionType.PROCESS_AGENT_TOOL_SEARCH_RESULT)

        response = await self.llm.generate(context, prompt)
        response_text, proposed_next_action, next_action_parameters = self.parse_response(
            response, ActionType.PROCESS_AGENT_TOOL_SEARCH_RESULT)

        retries = 0
        while proposed_next_action not in available_next_actions and retries < self.ACTION_MAX_RETRIES:
            retries += 1
            response = await self.llm.generate(context, prompt)
            response_text, proposed_next_action, next_action_parameters = self.parse_response(
                response, ActionType.PROCESS_AGENT_TOOL_SEARCH_RESULT)

        if retries == self.ACTION_MAX_RETRIES:
            raise ValueError(
                f"Failed to get a valid next action after {self.ACTION_MAX_RETRIES} retries")

        return response_text, proposed_next_action, next_action_parameters

    async def run_agent_tool_execution_action(self, action_parameters: Optional[Dict[Any, Any]] = None) -> Tuple[str, ActionType, Optional[Dict[Any, Any]]]:
        if not self.gateway_tools.session_id:
            # panic, we should never be executing a tool without a session ID since we should create when we search for tools
            raise ValueError("Gateway tools session ID is not set")

        assert action_parameters is not None, "action_parameters is required for AGENT_TOOL_EXECUTION"
        assert isinstance(
            action_parameters, dict), f"action_parameters is not a dict: {action_parameters}. It is a {type(action_parameters)}"
        assert "tool_name" in action_parameters, "tool_name is required for AGENT_TOOL_EXECUTION"
        assert "tool_args" in action_parameters, "tool_args is required for AGENT_TOOL_EXECUTION"
        tool_name = action_parameters["tool_name"]
        tool_args = action_parameters["tool_args"]

        result = await self.gateway_tools.execute_tool(tool_name, **tool_args)
        # Return the action_parameters so we can capture tool info in memory
        return result, ActionType.PROCESS_AGENT_TOOL_EXECUTION_RESULT, action_parameters

    async def run_process_agent_tool_execution_result_action(self, context: str, available_next_actions: List[ActionType]) -> Tuple[str, ActionType, Optional[Dict[Any, Any]]]:
        prompt = self.get_prompt(
            ActionType.PROCESS_AGENT_TOOL_EXECUTION_RESULT)

        response = await self.llm.generate(context, prompt)
        response_text, proposed_next_action, next_action_parameters = self.parse_response(
            response, ActionType.PROCESS_AGENT_TOOL_EXECUTION_RESULT)

        retries = 0
        while proposed_next_action not in available_next_actions and retries < self.ACTION_MAX_RETRIES:
            retries += 1
            response = await self.llm.generate(context, prompt)
            response_text, proposed_next_action, next_action_parameters = self.parse_response(
                response, ActionType.PROCESS_AGENT_TOOL_EXECUTION_RESULT)

        if retries == self.ACTION_MAX_RETRIES:
            raise ValueError(
                f"Failed to get a valid next action after {self.ACTION_MAX_RETRIES} retries")

        return response_text, proposed_next_action, next_action_parameters

    async def run_agent_response_action(self, context: str, available_next_actions: List[ActionType]) -> Tuple[str, ActionType, Optional[Dict[Any, Any]]]:
        prompt = self.get_prompt(ActionType.AGENT_RESPONSE)

        response = await self.llm.generate(context, prompt)
        response_text, proposed_next_action, _ = self.parse_response(
            response, ActionType.AGENT_RESPONSE)

        return response_text, proposed_next_action, None

    async def run_summarize_step(self) -> str:
        prompt = self.get_prompt(ActionType.STEP_SUMMARY)

        response = await self.llm.generate(self.memory.get_context(), prompt)
        response_text, _, _ = self.parse_response(
            response, ActionType.STEP_SUMMARY)

        return response_text

    def get_available_next_actions(self, action_type: ActionType):
        # the following state transitions can occur:
        # PROCESS_USER_INPUT --> AGENT_PLANNING | AGENT_TOOL_SEARCH | AGENT_TOOL_EXECUTION | AGENT_RESPONSE
        # AGENT_PLANNING --> AGENT_TOOL_SEARCH | AGENT_RESPONSE
        # AGENT_TOOL_SEARCH --> AGENT_PLANNING | AGENT_TOOL_EXECUTION | AGENT_RESPONSE
        # AGENT_TOOL_EXECUTION --> AGENT_PLANNING | AGENT_RESPONSE
        # AGENT_RESPONSE --> PROCESS_USER_INPUT | AWAIT_USER_INPUT
        # AWAIT_USER_INPUT --> (exits loop, no next actions)

        if action_type == ActionType.PROCESS_USER_INPUT:
            return [ActionType.AGENT_PLANNING, ActionType.AGENT_TOOL_SEARCH, ActionType.AGENT_TOOL_EXECUTION, ActionType.AGENT_RESPONSE]
        elif action_type == ActionType.AGENT_PLANNING:
            return [ActionType.AGENT_TOOL_SEARCH, ActionType.AGENT_RESPONSE]
        elif action_type == ActionType.PROCESS_AGENT_TOOL_SEARCH_RESULT:
            return [ActionType.AGENT_PLANNING, ActionType.AGENT_TOOL_EXECUTION, ActionType.AGENT_RESPONSE]
        elif action_type == ActionType.PROCESS_AGENT_TOOL_EXECUTION_RESULT:
            return [ActionType.AGENT_PLANNING, ActionType.AGENT_RESPONSE]
        elif action_type == ActionType.AGENT_RESPONSE:
            return [ActionType.PROCESS_USER_INPUT, ActionType.AWAIT_USER_INPUT]
        elif action_type == ActionType.AWAIT_USER_INPUT:
            return []  # No next actions - exits the loop

    async def run_action(self, user_input: str, context: str, action_type: ActionType, action_parameters: Optional[Dict[Any, Any]] = None) -> Tuple[str, ActionType, Optional[Dict[Any, Any]]]:
        available_next_actions = self.get_available_next_actions(action_type)
        if action_type == ActionType.PROCESS_USER_INPUT:
            return await self.run_process_user_input_action(
                user_input, context, available_next_actions)
        elif action_type == ActionType.AGENT_PLANNING:
            return await self.run_agent_planning_action(context, available_next_actions)
        elif action_type == ActionType.AGENT_TOOL_SEARCH:
            return await self.run_agent_tool_search_action(action_parameters)
        elif action_type == ActionType.AGENT_TOOL_EXECUTION:
            return await self.run_agent_tool_execution_action(
                action_parameters)
        elif action_type == ActionType.PROCESS_AGENT_TOOL_SEARCH_RESULT:
            return await self.run_process_agent_tool_search_result_action(context, available_next_actions)
        elif action_type == ActionType.PROCESS_AGENT_TOOL_EXECUTION_RESULT:
            return await self.run_process_agent_tool_execution_result_action(context, available_next_actions)
        elif action_type == ActionType.AGENT_RESPONSE:
            return await self.run_agent_response_action(context, available_next_actions)
        elif action_type == ActionType.AWAIT_USER_INPUT:
            # Return empty response and same action type
            return "", ActionType.AWAIT_USER_INPUT, None
        else:
            raise ValueError(f"Invalid action type: {action_type}")

    async def run_step(self, user_input: str):
        print(f"\n{'='*50}")
        print(f"STARTING AGENT STEP")
        print(f"{'='*50}")

        # TODO: handle memory updates
        action_type = ActionType.PROCESS_USER_INPUT
        previous_action_type = action_type
        action_count = 0
        action_parameters = None
        while action_count < self.MAX_ACTIONS:
            action_count += 1
            print(f"\nStep {action_count}/{self.MAX_ACTIONS}")
            print(f"Current Action: {action_type.value}")

            context = await self.get_context()
            print(f"Context length: {len(context) if context else 0} chars")
            print(f"Context: \n{context}")

            result, action_type, action_parameters = await self.run_action(user_input, context, action_type, action_parameters)

            # Extract tool_search_query from action_parameters if present
            tool_search_query = None
            if action_parameters and "tool_search_query" in action_parameters:
                tool_search_query = action_parameters["tool_search_query"]

            await self.memory.add_action(result, previous_action_type,
                                         action_parameters=action_parameters,
                                         tool_search_query=tool_search_query)
            previous_action_type = action_type

            print(f"Result: {result}")
            print(f"Next Action: {action_type.value}")
            print(f"Action Parameters: {action_parameters}")

            # Exit immediately if AWAIT_USER_INPUT is triggered
            if action_type == ActionType.AWAIT_USER_INPUT:
                print(f"Awaiting user input - stopping step")
                break

        # print(f"\nRunning summarize step...")
        summary = await self.run_summarize_step()
        self.memory.add_action(summary, ActionType.STEP_SUMMARY)
        print(f"Step completed!\n")
        print(f"{'='*50}")

    async def run(self):
        print("Agent is running. Type 'exit' to quit.")
        while True:
            user_input = input("You: ")
            if user_input.strip().lower() == "exit":
                print("Exiting agent.")
                import datetime
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"agent_context_{timestamp}.txt"
                context = self.memory.get_context()
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(context)
                print(f"Agent context saved to {filename}")
                break
            await self.memory.add_action(user_input, ActionType.USER_INPUT)
            await self.run_step(user_input)
        pass


if __name__ == "__main__":
    agent = Agent()
    asyncio.run(agent.run())

import asyncio
from typing import Any

from pydantic import BaseModel, Field

from config import Config
from dataclasses import dataclass
from tools import Tool, ToolInvocation
from tools.base import ToolResult, ToolKind

class SubagentParams(BaseModel):
    goal: str = Field(
        ...,
        description='The specific task or goal for the subagent to accomplish or achieve.'
    )

@dataclass
class SubagentDefinition:
    name: str
    description: str
    goal_prompt: str
    allowed_tools: list[str] | None = None
    max_turns: int = 20
    timeout_seconds: float = 600

class SubAgentTool(Tool):
    def __init__(self, config: Config, definition: SubagentDefinition):
        super().__init__(config)

        self.definition = definition
    
    @property
    def name(self) -> str:
        return f"subagent_{self.definition.name}"

    @property
    def description(self) -> str:
        return self.definition.description

    schema = SubagentParams
    kind = ToolKind.SUBAGENT

    def is_mutating(self, params: dict[str, Any]) -> bool:
        return True
    
    async def execute(self, invocation: ToolInvocation) -> ToolResult:

        from agent.agent import Agent
        from agent.events import AgentEventType
        
        params = SubagentParams(**invocation.params)

        if not params.goal:
            return ToolResult.error_result(
                'No goal or task was specified for a subagent'
            )
        
        config_dict = self.config.to_dict()
        config_dict['max_turns'] = self.definition.max_turns
        if self.definition.allowed_tools:
            config_dict['allowed_tools'] = self.definition.allowed_tools
        
        subagent_config = Config(**config_dict)

        prompt = f"""

        You are a specialized sub-agent with a specific task to complete.

        The prompt is: {self.definition.goal_prompt}

        Your Task/Goal is TO: 
        {params.goal}

        IMPORTANT CRITERIA:
        - Focus only on completing that specific task, don't wander or astray from it.
        - Do not engage in unrelated actions that are not pertinent to the task.
        - Once you have completed the task, goal, or have an answer for the user, display and provide your final response to the user.
        - Be concise and direct in your output.

        """

        tool_calls = []
        final_response = None
        error = None
        terminate_response = 'goal'

        try:
            async with Agent(subagent_config) as agent:
                timeout = asyncio.get_event_loop().time() + self.definition.timeout_seconds
                async for event in agent.run(prompt):
                    if asyncio.get_event_loop().time() > timeout:
                        terminate_response = 'timeout'
                        final_response = 'Sub-agent timed out'
                        break

                    if event.type == AgentEventType.TOOL_CALL_START:
                        tool_calls.append(event.data.get('name'))
                    elif event.type == AgentEventType.TEXT_COMPLETE:
                        final_response = event.data.get('content')
                    elif event.type == AgentEventType.AGENT_END:
                        if final_response is None:
                            final_response = event.data.get('response')
                    elif event.type == AgentEventType.AGENT_ERROR:
                        terminate_response = 'error'
                        error = event.data.get('error', 'Unknown')
                        final_response = f"Sub-agent error: {error}"
                        break
        except Exception as e:
            terminate_response = 'error'
            error = str(e)
            final_response = f"Sub-agent failed: {e}"
        
        result = f"""Sub-agent '{self.definition.name}' completed.

        Termination: {terminate_response}
        Tools called: {', '.join(tool_calls) if tool_calls else 'None'}

        Result: 
        {final_response or 'No response'}

        """

        if error:
            return ToolResult.error_result(
                result
            )
        
        return ToolResult.success_result(
            result
        )

CODEBASE_INVESTIGATOR = SubagentDefinition(

    name='codebase_investigator',
    description='Investigates the codebase to answer question about code structure, or is a pre-req for code review.',
    goal_prompt="""

    You are a codebase investigation specialist. Your job is soley to explore and understand code to answer questions.
    Use tools that can only read files, ex: read, grep, glob, and directories to investigation.
    I repeat, DO NOT modify any files.

    """,

    allowed_tools=[
        "read_file", 
        "grep", "glob", 
        "list_dir"
    ],

    max_turns=15
)

CODE_REVIEWER = SubagentDefinition(

    name = 'code_reviewer',
    description='Reviews code changes and provides feedback on quality, bugs and improvements upon the request of the user',
    goal_prompt="""

    You are a code review specialist. Your job is to review code and provide constructive feedback to the user. 
    Look for bugs, inconsistent or non-clean code, security vulnerabilities or issues, and improvement opportunities.
    Use read_file, list_dir and grep to examine the code.

    """,

    allowed_tools=[
        "read_file", 
        "grep", 
        "list_dir"
    ],

    max_turns=10,
    timeout_seconds=300

)

SOFTWARE_ARCHITECT = SubagentDefinition(

    name = 'software_architect',
    description="Changes code based on the user's prompt, provides clean and quality code and does not stray away from the codestyle written by the developer of the project.",

    goal_prompt="""

    You are a software architect. Your job is to maintain quality code in the codebase and write functional code. 
    Read before you write, implement code based on user's request.
    Especially, use the todo tool when tasks get complicated or long.
    You can give back feedback of code if necessary Tools that can be called and used are
    read_file, list_dir, grep, glob, write, edit, todo

    """,

    allowed_tools=[
        'read_file', 
        'list_dir', 
        'grep', 
        'glob', 
        'write', 
        'edit', 
        'todo'
    ],

    max_turns=10
)

TEST_WRITER = SubagentDefinition(

    name = 'test_writer',
    description="Creates tests upon the user's request to make tests for their code. Make sure to test for edge cases and specific ways the code can error.",

    goal_prompt=""""

    You are a code test writer, your speciality is in writing tests for the user to put their code against edge cases, and special areas where their code
    can fail.

    Especially, use tools like todo to plan out multiple tests if neccessary, tools you can call are read_file, list_dir, grep, glob, write, edit, shell, and todo.

    """,

    allowed_tools=[
        'read_file',
        'list_dir',
        'grep',
        'glob',
        'write',
        'todo',
        'edit',
        'shell'
    ],

    max_turns=10
)

DEBUGGER = SubagentDefinition(

    name = "debugger",
    description="You are a debugger, you help find errors or incosistencies in code then use tools like read, write, and edit to fix files.",
    goal_prompt="""

    You are a professional debugger. Your purpose in working with the user is to find bugs of any severity in the code.
    Use the todo tool when debugging gets complex or long.
    Use tools such as: grep, glob, write, edit, read, todo

    """,

    allowed_tools=[
        'grep',
        'glob',
        'write',
        'edit',
        'read',
        'todo'
    ],

    max_turns=10

)

# Will add more subagent definitions

def get_default_subagent_definitions() -> list[SubagentDefinition]:
    return [
        CODEBASE_INVESTIGATOR,
        CODE_REVIEWER,
        SOFTWARE_ARCHITECT,
        TEST_WRITER,
        DEBUGGER,
    ]
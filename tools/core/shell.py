import asyncio
import os
import fnmatch
from pathlib import Path
import signal
import sys

from pydantic import BaseModel, Field

from tools.base import Tool, ToolConfirmation, ToolInvocation, ToolKind, ToolResult

DANGEROUS_COMMANDS = {
    "rm -rf /",
    "rm -rf ~",
    "rm -rf /*",
    "dd if=/dev/zero",
    "dd if=/dev/random",
    "mkfs",
    "fdisk",
    "parted",
    ":(){ :|:& };:",  
    "chmod 777 /",
    "chmod -R 777",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "init 0",
    "init 6",
    "sleep",
}

class ShellParams(BaseModel):

    command: str = Field(
        ...,
        description='The shell command used to execute system commands',
    )

    timeout: int = Field(
        120,
        ge=1,
        le=600,
        description='Timeout in seconds (defaulted: 120s)'
    )

    cwd: str | None = Field(
        None,
        description='The working directory for the command to be ran'
    )

class ShellTool(Tool):

    name = 'shell'
    kind = ToolKind.SHELL
    description = "Execute a shell command. Use this for running system wide commands, scripts and usage of CLI Tools."

    schema = ShellParams

    async def get_confirmation(self, invocation: ToolInvocation) -> ToolConfirmation:
        params = ShellParams(**invocation.params)

        command = params.command.lower().strip()
        for dangerous in DANGEROUS_COMMANDS:
            if dangerous in command:
                return ToolConfirmation(
                    tool_name=self.name,
                    params=invocation.params,
                    description=f"Execute (DANGEROUS): {params.command}",
                    command=params.command,
                    is_dangerous=True,
                )

        return ToolConfirmation(
            tool_name=self.name,
            params=invocation.params,
            description=f"Execute: {params.command}",
            command=params.command,
            is_dangerous=False,
        )

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = ShellParams(**invocation.params)

        command = params.command.lower().strip()
        for dangerous in DANGEROUS_COMMANDS:
            if dangerous in command:
                return ToolResult.error_result(
                    f'Command blocked: {params.command}',
                    metadata = {
                        'blocked': True
                    }
                )
        
        if params.cwd:
            cwd = Path(params.cwd)
            if not cwd.is_absolute():
                cwd = invocation.cwd / cwd
        else:
            cwd = invocation.cwd
        
        if not cwd.exists():
            return ToolResult.error_result(
                f"Working directory doesn't exist: {cwd}"
            )
        
        env = self._build_environment()
        if sys.platform == 'win32':
            shell_cmd = ['cmd.exe', '/c', params.command]
        else:
            shell_cmd = ['/bin/bash', '-c', params.command]
        
        process = await asyncio.create_subprocess_exec(
            *shell_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
            start_new_session=True,
        )
        try:
            stdout_data, stderr_data = await asyncio.wait_for(
                process.communicate(),
                timeout = params.timeout
            )
        except asyncio.TimeoutError:
            if sys.platform != 'win32':
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            else:
                process.kill()
            await process.wait()
            return ToolResult.error_result(
                f'Command timed out after: {params.timeout}'
            )
        
        exit_code = process.returncode

        stdout = stdout_data.decode(
            'utf-8',
            errors='replace'
        )

        stderr = stderr_data.decode(
            'utf-8',
            errors='replace'
        )

        output = ""
        if stdout.strip():
            output += stdout.rstrip()
        
        if stderr.strip():
            output += "\n--- stderr ---\n"
            output += stderr.rstrip()
        
        if exit_code != 0:
            output += f'\nExit code: {exit_code}'
        
        if len(output) > 100*1024:
            output = output[: 100 * 1024] + "\n.. [output truncated]"
        
        return ToolResult(
            success=exit_code==0,
            output=output,
            error=stderr if exit_code != 0 else None,
            exit_code=exit_code,
        )

    def _build_environment(self) -> dict[str, str]:
        env = os.environ.copy()

        shell_environment = self.config.shell_environment

        if not shell_environment.ignore_default_excludes:
            for pattern in shell_environment.exclude_patterns:
                keys_to_remove = [k for k in env.keys() if fnmatch.fnmatch(k.upper(), pattern.upper())]

                for k in keys_to_remove:
                    del env[k]

        if shell_environment.set_vars:
            env.update(shell_environment.set_vars)

        return env

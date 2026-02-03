import asyncio
import os
from typing import List, Any
from e2b_code_interpreter import AsyncSandbox as E2BAsyncSandbox
from sandbox_interface import BaseSandbox, CommandResult, FileInfo

class E2BAdapter(BaseSandbox):
    def __init__(self, template: str = "code-interpreter-v1"):
        self.template = template
        self.sandbox: E2BAsyncSandbox | None = None

    async def start(self):
        if not self.sandbox:
            self.sandbox = await E2BAsyncSandbox.create(self.template)

    async def stop(self):
        if self.sandbox:
            await self.sandbox.kill()
            self.sandbox = None

    async def is_running(self) -> bool:
        if not self.sandbox:
            return False
        return await self.sandbox.is_running()

    @property
    def id(self) -> str:
        return self.sandbox.sandbox_id if self.sandbox else "unknown"

    async def run_code(self, code: str, language: str = "python") -> Any:
        # E2B supports run_code directly
        return await self.sandbox.run_code(code)

    async def run_command(self, command: str, background: bool = False) -> CommandResult:
        res = await self.sandbox.commands.run(command, background=background)
        return CommandResult(
            stdout=res.stdout,
            stderr=res.stderr,
            exit_code=res.exit_code,
            pid=res.pid
        )

    async def list_files(self, path: str) -> List[FileInfo]:
        files = await self.sandbox.files.list(path)
        return [FileInfo(name=f.name, type="dir" if f.type == "dir" else "file") for f in files]

    async def read_file(self, path: str, format: str = "text") -> str | bytes:
        return await self.sandbox.files.read(path, format=format)

    async def write_file(self, path: str, content: str | bytes):
        await self.sandbox.files.write(path, content)

    async def get_host(self, port: int) -> str:
        return self.sandbox.get_host(port)

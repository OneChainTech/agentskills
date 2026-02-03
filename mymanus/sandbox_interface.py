from abc import ABC, abstractmethod
from typing import List, Optional, Any
from dataclasses import dataclass
import base64

@dataclass
class CommandResult:
    stdout: str
    stderr: str
    exit_code: int
    pid: Optional[int] = None

@dataclass
class FileInfo:
    name: str
    type: str  # 'file' or 'dir'

class BaseSandbox(ABC):
    @abstractmethod
    async def start(self):
        """Start the sandbox session."""
        pass

    @abstractmethod
    async def stop(self):
        """Stop the sandbox session."""
        pass

    @abstractmethod
    async def is_running(self) -> bool:
        """Check if sandbox is running."""
        pass
        
    @property
    @abstractmethod
    def id(self) -> str:
        """Get sandbox ID."""
        pass

    # --- Capabilities ---

    @abstractmethod
    async def run_code(self, code: str, language: str = "python") -> Any:
        """Run code. Returns execution result object (E2B-style or similar wrapper)."""
        pass

    @abstractmethod
    async def run_command(self, command: str, background: bool = False) -> CommandResult:
        """Run shell command."""
        pass

    @abstractmethod
    async def list_files(self, path: str) -> List[FileInfo]:
        """List files."""
        pass

    @abstractmethod
    async def read_file(self, path: str, format: str = "text") -> str | bytes:
        """Read file content."""
        pass

    @abstractmethod
    async def write_file(self, path: str, content: str | bytes):
        """Write content to file."""
        pass

    @abstractmethod
    async def get_host(self, port: int) -> str:
        """Get external host for a port."""
        pass

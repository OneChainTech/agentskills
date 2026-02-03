import asyncio
import os
import base64
from typing import List, Any
from datetime import timedelta

try:
    from opensandbox.sandbox import Sandbox
    from opensandbox.config import ConnectionConfig
    from opensandbox.models.filesystem import SearchEntry
    from code_interpreter import CodeInterpreter, SupportedLanguage
    HAS_OPENSANDBOX = True
except ImportError:
    HAS_OPENSANDBOX = False
    Sandbox = None
    SearchEntry = None

from sandbox_interface import BaseSandbox, CommandResult, FileInfo

# Helper classes for consistent return format
class ExecutionLog:
    def __init__(self, out, err):
        self.stdout = out
        self.stderr = err

class ErrorObj:
    def __init__(self, name, value, traceback):
        self.name = name
        self.value = value
        self.traceback = traceback

class ExecutionResult:
    def __init__(self, logs, error=None):
        self.logs = logs
        self.results = [] # Not used by mymanus agent currently
        self.error = error

class OpenSandboxAdapter(BaseSandbox):
    def __init__(self, image: str = "opensandbox/code-interpreter:v1.0.1"):
        self.image = image
        self.sandbox = None
        self.interpreter = None
        self.python_path = "python3" # Default
        self._provider_name = "opensandbox"

    async def start(self):
        if not HAS_OPENSANDBOX:
            raise RuntimeError("OpenSandbox SDK not installed. Please install 'opensandbox' and 'opensandbox-code-interpreter'.")
        
        domain = os.getenv("OPEN_SANDBOX_DOMAIN", "127.0.0.1:8082")
        api_key = os.getenv("OPEN_SANDBOX_API_KEY", "")
        
        print(f"[OpenSandbox] Connecting to {domain}...")
        
        try:
            config = ConnectionConfig(
                domain=domain,
                api_key=api_key,
                request_timeout=timedelta(seconds=300)
            )
            
            # Create sandbox with Code Interpreter support
            self.sandbox = await Sandbox.create(
                self.image,
                connection_config=config,
                entrypoint=["/opt/opensandbox/code-interpreter.sh"],
                env={
                    "PYTHON_VERSION": "3.12",
                    "PIP_BREAK_SYSTEM_PACKAGES": "1",
                    "GRADIO_SERVER_NAME": "0.0.0.0",
                    "GRADIO_ROOT_PATH": "/proxy/7860" 
                }
            )
            
            # Initialize Code Interpreter
            self.interpreter = await CodeInterpreter.create(self.sandbox)
            
            # Detect actual Python path
            try:
                res = await self.interpreter.codes.run("import sys; print(sys.executable)", language=SupportedLanguage.PYTHON)
                if res.logs and res.logs.stdout:
                    self.python_path = res.logs.stdout[0].text.strip()
                    print(f"[OpenSandbox] Detected Python path: {self.python_path}")
            except Exception as e:
                print(f"[OpenSandbox] Warning: Failed to detect Python path: {e}")

            # Ensure /home/user exists and links to /workspace (compatibility)
            try:
                # Force symlink /home/user -> /workspace so paths are interchangeable
                await self.run_command("mkdir -p /home")
                await self.run_command("rm -rf /home/user")
                await self.run_command("ln -s /workspace /home/user")
            except Exception as e:
                print(f"[OpenSandbox] Warning: Failed to symlink /home/user: {e}")

            print(f"[OpenSandbox] Sandbox created: {self.sandbox.id}")
            
        except Exception as e:
            print(f"[OpenSandbox] Connection Error: {e}")
            raise RuntimeError(
                f"Failed to connect to OpenSandbox Daemon at '{domain}'.\n"
                f"Ensure the service is running locally (e.g., via Docker) or configured correctly.\n"
                f"Error details: {str(e)}"
            )

    async def stop(self):
        if self.sandbox:
            await self.sandbox.kill()
            self.sandbox = None
            self.interpreter = None

    async def is_running(self) -> bool:
        if not self.sandbox:
            return False
        return await self.sandbox.is_healthy()

    @property
    def id(self) -> str:
        return self.sandbox.id if self.sandbox else "unknown"

    async def run_code(self, code: str, language: str = "python") -> Any:
        if not self.interpreter:
            raise RuntimeError("CodeInterpreter not initialized")

        try:
            # Execute code using the interpreter
            result = await self.interpreter.codes.run(code, language=SupportedLanguage.PYTHON)
            
            stdout_list = []
            stderr_list = []
            
            # Process logs
            if result.logs:
                if result.logs.stdout:
                    stdout_list = [msg.text for msg in result.logs.stdout]
                if result.logs.stderr:
                    stderr_list = [msg.text for msg in result.logs.stderr]
            
            # Process final result
            if result.result:
                # Add return value to stdout
                for res in result.result:
                    if res.text:
                        stdout_list.append(res.text)

            error_obj = None
            if result.error:
                 # Safely get error attributes, falling back if they don't exist
                 err_msg = getattr(result.error, "message", getattr(result.error, "value", str(result.error)))
                 err_tb = getattr(result.error, "stack_trace", getattr(result.error, "traceback", ""))
                 
                 error_obj = ErrorObj("ExecutionError", err_msg, err_tb)

            return ExecutionResult(ExecutionLog(stdout_list, stderr_list), error_obj)

        except Exception as e:
            # Fallback wrapper
            return ExecutionResult(
                ExecutionLog([], []), 
                ErrorObj("OpenSandboxExecutionError", str(e), "")
            )

    async def run_command(self, command: str, background: bool = False) -> CommandResult:
        if not self.sandbox:
            raise RuntimeError("Sandbox not started")
            
        # Ensure the correct Python bin directory is in PATH
        bin_dir = os.path.dirname(self.python_path)
        if bin_dir and bin_dir != "/usr/bin":
            real_cmd = f"export PATH={bin_dir}:$PATH && {command}"
        else:
            real_cmd = command
            
        if background:
            # Use nohup to prevent SIGHUP when the shell exits
            # We wrap the command in sh -c to ensure complex commands work with nohup
            # Redirect output to a log file so it doesn't hang the pipe and we can debug
            real_cmd = f"nohup sh -c '{real_cmd}' > /workspace/background.log 2>&1 & echo $!"
            
        res = await self.sandbox.commands.run(real_cmd)
        
        stdout_list = []
        stderr_list = []
        
        # Process logs
        if getattr(res, 'logs', None):
            if res.logs.stdout:
                stdout_list = [msg.text for msg in res.logs.stdout]
            if res.logs.stderr:
                stderr_list = [msg.text for msg in res.logs.stderr]
        
        stdout = "".join(stdout_list)
        stderr = "".join(stderr_list)
        
        # OpenSandbox Execution object does not have 'exit_code'.
        # Non-zero exit codes are returned as ExecutionError with the code in 'value'.
        exit_code = 0
        error_msg = ""
        if getattr(res, 'error', None):
            try:
                # If value is digits, it's likely the exit code (e.g. "1", "127")
                if res.error.value and res.error.value.isdigit():
                    exit_code = int(res.error.value)
                else:
                    # If it's a text error message (e.g. "executable not found"), treat as error
                    exit_code = 1
                    error_msg = res.error.value
            except:
                exit_code = 1
                error_msg = str(res.error)

        # If we have an error message but no stderr (e.g. spawn failure), inject it
        if error_msg and not stderr:
            stderr = f"Execution Error: {error_msg}"
        
        pid = None
        if background and stdout:
            try:
                # Try to parse PID from the last line of stdout if we appended "& echo $!"
                # Note: This is a best-effort heuristic.
                lines = stdout.strip().splitlines()
                if lines:
                    pid = int(lines[-1].strip())
            except:
                pass
                
        return CommandResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            pid=pid
        )

    async def list_files(self, path: str) -> List[FileInfo]:
        try:
            # Use OpenSandbox search API with SearchEntry
            entry = SearchEntry(path=path, pattern="*")
            entries = await self.sandbox.files.search(entry)
            files = []
            for e in entries:
                # Adapt EntryInfo to FileInfo
                # EntryInfo has: path, is_dir, size, mode, mtime
                name = e.path.split('/')[-1] if e.path else e.path
                ftype = "dir" if e.is_dir else "file"
                files.append(FileInfo(name=name, type=ftype))
            return files
        except Exception as e:
            # Fallback to ls
            res = await self.run_command(f"ls -F {path}")
            files = []
            if res.exit_code == 0:
                for line in res.stdout.splitlines():
                    line = line.strip()
                    if not line: continue
                    if line.endswith('/'):
                        files.append(FileInfo(name=line[:-1], type="dir"))
                    elif line.endswith('*'):
                        files.append(FileInfo(name=line[:-1], type="file"))
                    else:
                        files.append(FileInfo(name=line, type="file"))
            return files

    async def read_file(self, path: str, format: str = "text") -> str | bytes:
        # OpenSandbox SDK has both read_file (returns str) and read_bytes (returns bytes)
        try:
            if format == "bytes":
                return await self.sandbox.files.read_bytes(path)
            else:
                return await self.sandbox.files.read_file(path, encoding="utf-8")
        except Exception as e:
            raise RuntimeError(f"Error reading file: {e}")

    async def write_file(self, path: str, content: str | bytes):
        # OpenSandbox SDK write_file supports str | bytes | IOBase
        try:
            await self.sandbox.files.write_file(path, content, encoding="utf-8")
        except Exception as e:
            raise RuntimeError(f"Error writing file: {e}")

    async def get_host(self, port: int) -> str:
        if not self.sandbox:
            raise RuntimeError("Sandbox not started")

        try:
            # OpenSandbox SDK get_endpoint returns a SandboxEndpoint object
            # SandboxEndpoint usually has 'endpoint' field (host:port) or similar
            # Based on SDK code: 
            #   get_endpoint(port) -> SandboxEndpoint
            # We need to verify what SandboxEndpoint contains. 
            # Usually it's an object with .endpoint or .uri
            endpoint_obj = await self.sandbox.get_endpoint(port)
            
            # The SDK definition says it returns SandboxEndpoint.
            # We assume it has an 'endpoint' attribute which is string "host:port"
            if hasattr(endpoint_obj, 'endpoint'):
                return endpoint_obj.endpoint
            
            # Fallback if attribute differs
            return str(endpoint_obj)
            
        except Exception as e:
            print(f"Error getting endpoint from OpenSandbox: {e}")
            # Fallback for local Docker mode where ports might be mapped directly 
            # or if using host networking.
            # For now, return localhost:port as a reasonable default for local dev
            return f"localhost:{port}"

from mcp.server.fastmcp import FastMCP
from e2b_code_interpreter import AsyncSandbox
import asyncio
import os
import logging
import re
from dotenv import load_dotenv

# Configure logging to stderr to avoid interfering with MCP stdout
logging.basicConfig(level=logging.ERROR)

# Load env to ensure E2B_API_KEY is available
load_dotenv()

# Initialize FastMCP
mcp = FastMCP("E2B_Firecracker_Sandbox")

# Global sandbox instance
GLOBAL_SANDBOX = None
STATIC_SERVER_PORT = 8000
SERVER_STARTED = False

async def get_or_create_sandbox():
    """Get the running E2B sandbox or create a new one."""
    global GLOBAL_SANDBOX
    
    # Check if key is set
    if not os.getenv("E2B_API_KEY"):
        raise RuntimeError("E2B_API_KEY not found in environment variables. Please set it in your .env file.")

    if GLOBAL_SANDBOX:
        return GLOBAL_SANDBOX

    # Create new AsyncSandbox
    try:
        GLOBAL_SANDBOX = await AsyncSandbox.create()
    except Exception as e:
        raise RuntimeError(f"Failed to create E2B Sandbox: {e}")
        
    return GLOBAL_SANDBOX

@mcp.tool()
async def run_code(code: str) -> str:

    """
    Executes Python code in a secure Firecracker MicroVM via E2B.
    Variables are preserved between calls in the same session.
    
    Args:
        code: The Python code to execute.
    """
    try:
        sb = await get_or_create_sandbox()
        
        execution = await sb.run_code(code)
        
        output = []
        if execution.logs.stdout:
            output.append("STDOUT:\n" + "\n".join(execution.logs.stdout))
        if execution.logs.stderr:
            output.append("STDERR:\n" + "\n".join(execution.logs.stderr))
            
        if execution.results:
            for result in execution.results:
                # result is an object, we convert to string representation
                output.append(f"RESULT: {str(result)}")
                
        if execution.error:
            output.append(f"ERROR: {execution.error.name}: {execution.error.value}\n{execution.error.traceback}")
            
        return "\n".join(output) if output else "(Code executed successfully with no output)"

    except Exception as e:
        return f"E2B Execution Error: {str(e)}"

@mcp.tool()
async def run_shell_command(command: str, is_background: bool = False) -> str:
    """
    Executes a shell command in the E2B sandbox.
    
    Args:
        command: The shell command to execute (e.g. 'pip install numpy', 'ls -la').
        is_background: Set to True to run the command in the background (e.g. for starting servers).
    """
    try:
        sb = await get_or_create_sandbox()
        
        if is_background:
            # Execute in background and return PID immediately
            cmd_handle = await sb.commands.run(command, background=True)
            return f"Command '{command}' started in background. PID: {cmd_handle.pid}"
        
        exec_result = await sb.commands.run(command)
        
        output = []
        if exec_result.stdout:
            output.append(f"STDOUT:\n{exec_result.stdout}")
        if exec_result.stderr:
            output.append(f"STDERR:\n{exec_result.stderr}")
            
        if exec_result.exit_code != 0:
            output.append(f"Exit Code: {exec_result.exit_code}")
            
        return "\n".join(output) if output else "(Command executed successfully)"

    except Exception as e:
        return f"E2B Shell Error: {str(e)}"

@mcp.tool()
async def restart_sandbox() -> str:
    """Kills and recreates the E2B sandbox."""
    global GLOBAL_SANDBOX
    if GLOBAL_SANDBOX:
        try:
            await GLOBAL_SANDBOX.kill()
        except: pass
        GLOBAL_SANDBOX = None
    return "E2B Sandbox restarted (old instance killed)."

@mcp.tool()
async def list_files(path: str = ".") -> str:
    """List files in the directory."""
    try:
        sb = await get_or_create_sandbox()
        files = await sb.files.list(path)
        return "\n".join([f"{f.name} ({f.type})" for f in files])
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def read_file(path: str) -> str:
    """Read a file as text."""
    try:
        sb = await get_or_create_sandbox()
        return await sb.files.read(path)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def write_file(path: str, content: str) -> str:
    """
    Write content to a file in the sandbox.
    Overwrites the file if it exists.
    """
    try:
        sb = await get_or_create_sandbox()
        # e2b write handles creating the file
        await sb.files.write(path, content)
        return f"File '{path}' written successfully."
    except Exception as e:
        return f"Error writing file: {str(e)}"

@mcp.tool()
async def upload_local_file(local_path: str, remote_path: str = None) -> str:
    """
    Uploads a file from the local machine (where the agent is running) to the E2B sandbox.
    Use this to load user-uploaded files into the analysis environment.
    
    Args:
        local_path: The absolute path to the file on the local server.
        remote_path: The destination path in the sandbox. Defaults to the filename.
    """
    try:
        sb = await get_or_create_sandbox()
        
        if not os.path.exists(local_path):
            return f"Error: Local file '{local_path}' not found."
            
        if not remote_path:
            remote_path = os.path.basename(local_path)
            
        with open(local_path, "rb") as f:
            file_data = f.read()
            
        await sb.files.write(remote_path, file_data)
        return f"File uploaded successfully to sandbox at '{remote_path}'"
    except Exception as e:
        return f"Error uploading file: {str(e)}"

@mcp.tool()
async def install_package(package_name: str) -> str:
    """
    Install a Python package using pip in the sandbox.
    """
    try:
        sb = await get_or_create_sandbox()
        # Use pip via shell command for reliability
        exec_result = await sb.commands.run(f"pip install {package_name}")
        
        output = []
        if exec_result.stdout:
            output.append(f"STDOUT:\n{exec_result.stdout}")
        if exec_result.stderr:
            output.append(f"STDERR:\n{exec_result.stderr}")
            
        if exec_result.exit_code != 0:
            output.append(f"Exit Code: {exec_result.exit_code}")
            
        return "\n".join(output) if output else "(Package installed successfully)"

    except Exception as e:
        return f"Error installing package: {str(e)}"

@mcp.tool()
async def visualize_file(path: str) -> str:
    """
    Expose a file via a public URL for visualization.
    Automatically starts a static file server in the sandbox if needed.
    """
    global SERVER_STARTED
    try:
        sb = await get_or_create_sandbox()
        
        # Start server if not running
        if not SERVER_STARTED:
            # We blindly try to start it. If port is taken, it might be us or user.
            # Using python -m http.server is lightweight and standard.
            await sb.commands.run(f"python3 -m http.server {STATIC_SERVER_PORT}", background=True)
            SERVER_STARTED = True
            
        # Get public host
        host = sb.get_host(STATIC_SERVER_PORT)
        url = f"https://{host}/{path}"
        
        # Determine MIME type for frontend hint (optional but good for UI logic)
        ext = path.split('.')[-1].lower() if '.' in path else 'txt'
        mime = "text/plain"
        if ext == "html": mime = "text/html"
        elif ext == "png": mime = "image/png"
        elif ext == "jpg" or ext == "jpeg": mime = "image/jpeg"
        elif ext == "svg": mime = "image/svg+xml"
        elif ext == "json": mime = "application/json"
        elif ext == "md": mime = "text/markdown"
        
        import json
        return json.dumps({
            "type": "file_preview",
            "path": path,
            "mime": "url", # Frontend handles this as an iframe src
            "content": url
        })
        
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def get_public_url(port: int) -> str:
    """Get a public URL for a port exposed in the sandbox."""
    try:
        sb = await get_or_create_sandbox()
        host = sb.get_host(port)
        return f"https://{host}"
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    mcp.run()

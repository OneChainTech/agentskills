from mcp.server.fastmcp import FastMCP
from e2b_code_interpreter import AsyncSandbox
import asyncio
import os
import logging
from dotenv import load_dotenv

# Configure logging to stderr to avoid interfering with MCP stdout
logging.basicConfig(level=logging.ERROR)

# Load env to ensure E2B_API_KEY is available
load_dotenv()

# Initialize FastMCP
mcp = FastMCP("E2B_Firecracker_Sandbox")

# Global sandbox instance
GLOBAL_SANDBOX = None

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
async def run_shell_command(command: str) -> str:
    """
    Executes a shell command in the E2B sandbox.
    
    Args:
        command: The shell command to execute (e.g. 'pip install numpy', 'ls -la').
    """
    try:
        sb = await get_or_create_sandbox()
        
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
    Read a file and return it as a visualization event for the user.
    Use this for HTML, Images, or other visual artifacts.
    Returns a JSON string identifying the content.
    """
    try:
        sb = await get_or_create_sandbox()
        
        # Determine MIME type based on extension
        ext = path.split('.')[-1].lower() if '.' in path else 'txt'
        mime = "text/plain"
        if ext == "html": mime = "text/html"
        elif ext == "png": mime = "image/png"
        elif ext == "jpg" or ext == "jpeg": mime = "image/jpeg"
        elif ext == "svg": mime = "image/svg+xml"
        elif ext == "json": mime = "application/json"
        elif ext == "md": mime = "text/markdown"
        
        content = ""
        is_binary = mime.startswith("image/")
        
        if is_binary:
            # Use shell to get base64 for images
            # -w 0 is important to avoid newlines in base64 output on Linux (alpine base64 usually behaves differently, so we strip manually)
            cmd = f"cat {path} | base64"
            exec_result = await sb.commands.run(cmd)
            if exec_result.exit_code != 0:
                return f"Error reading binary file: {exec_result.stderr}"
            # STRICTLY REMOVE NEWLINES to prevent JSON parse errors
            content = exec_result.stdout.replace("\n", "").replace("\r", "").strip()
        else:
            content = await sb.files.read(path)
            
        import json
        return json.dumps({
            "type": "file_preview",
            "path": path,
            "mime": mime,
            "content": content
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

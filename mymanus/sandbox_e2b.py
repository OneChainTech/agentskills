from mcp.server.fastmcp import FastMCP
from e2b_code_interpreter import AsyncSandbox
import asyncio
import os
from dotenv import load_dotenv

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
            GLOBAL_SANDBOX.close()
        except: pass
        GLOBAL_SANDBOX = None
    return "E2B Sandbox restarted (old instance closed)."

if __name__ == "__main__":
    mcp.run()

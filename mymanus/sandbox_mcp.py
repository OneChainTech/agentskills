from mcp.server.fastmcp import FastMCP
import asyncio
import uuid
import json
import subprocess
import os

# Initialize the MCP Server
mcp = FastMCP("DockerSandbox")

# Global state
CONTAINER_NAME = None
# Using the image confirmed to be present locally
IMAGE_NAME = "python:3.10.17-alpine3.21"

def run_cmd(cmd_list):
    """Run a system command and return output."""
    try:
        result = subprocess.run(
            cmd_list,
            capture_output=True,
            text=True,
            check=False
        )
        return result
    except Exception as e:
        class ErrorResult:
            def __init__(self, err):
                self.stdout = ""
                self.stderr = str(err)
                self.returncode = 1
        return ErrorResult(e)

async def get_or_start_container():
    global CONTAINER_NAME
    
    if CONTAINER_NAME:
        # Check if container is still running
        check = run_cmd(["docker", "inspect", "-f", "{{.State.Running}}", CONTAINER_NAME])
        if check.stdout.strip() == "true":
            return CONTAINER_NAME
        else:
            CONTAINER_NAME = None

    # Start new container
    name = "mcp-sandbox-" + str(uuid.uuid4())[:8]
    # Use tail -f /dev/null to keep container alive
    start_cmd = ["docker", "run", "-d", "--name", name, IMAGE_NAME, "tail", "-f", "/dev/null"]
    
    res = run_cmd(start_cmd)
    if res.returncode == 0:
        CONTAINER_NAME = name
        return name
    else:
        raise RuntimeError(f"Failed to start Docker container: {res.stderr}")

@mcp.tool()
async def run_shell_command(command: str) -> str:
    """
    Executes a shell command in a persistent Docker container.
    """
    try:
        name = await get_or_start_container()
        
        # Execute command via docker exec
        exec_cmd = ["docker", "exec", name, "sh", "-c", command]
        res = run_cmd(exec_cmd)
        
        output = []
        if res.stdout: output.append(f"STDOUT:\n{res.stdout}")
        if res.stderr: output.append(f"STDERR:\n{res.stderr}")
        if res.returncode != 0: output.append(f"Exit Code: {res.returncode}")
        
        return "\n".join(output) if output else "(No output)"
    except Exception as e:
        return f"Docker Error: {str(e)}"

@mcp.tool()
async def run_code(code: str) -> str:
    """
    Executes Python code in the persistent Docker container.
    Variables and files are preserved between calls.
    """
    try:
        name = await get_or_start_container()
        
        # Write code to a temporary file inside the container
        # Use base64 to avoid quoting issues
        import base64
        b64_code = base64.b64encode(code.encode('utf-8')).decode('utf-8')
        
        write_cmd = f"echo {b64_code} | base64 -d > /tmp/script.py"
        run_cmd(["docker", "exec", name, "sh", "-c", write_cmd])
        
        # Run the script
        return await run_shell_command("python3 /tmp/script.py")
    except Exception as e:
        return f"Python Execution Error: {str(e)}"

@mcp.tool()
async def restart_sandbox() -> str:
    """Stops and removes the current sandbox container."""
    global CONTAINER_NAME
    if CONTAINER_NAME:
        run_cmd(["docker", "stop", CONTAINER_NAME])
        run_cmd(["docker", "rm", CONTAINER_NAME])
        CONTAINER_NAME = None
        return "Sandbox container stopped and removed."
    return "No active sandbox to restart."

if __name__ == "__main__":
    mcp.run()

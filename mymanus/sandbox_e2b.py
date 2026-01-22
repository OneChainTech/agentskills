import asyncio
import base64
import json
import os
from typing import Optional, List, Dict, Any

from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from e2b_code_interpreter import AsyncSandbox
from e2b_desktop import Sandbox as DesktopSandbox

# Global Desktop Sandbox (Singleton for Server & Agent)
GLOBAL_DESKTOP_SANDBOX = None
DESKTOP_STREAM_STARTED = False

# Ensure E2B_API_KEY is available
if not os.getenv("E2B_API_KEY"):
    pass

# --- Code Interpreter / Standard Sandbox Helpers ---

def get_sandbox(config: RunnableConfig) -> AsyncSandbox:
    """Helper to extract sandbox from config."""
    sandbox = config.get("configurable", {}).get("sandbox")
    if not sandbox:
        raise RuntimeError("E2B Sandbox not found in configurable config.")
    return sandbox

# --- Desktop Sandbox Helpers ---

async def get_or_create_desktop_sandbox() -> DesktopSandbox:
    """Get the running E2B desktop sandbox or create a new one."""
    global GLOBAL_DESKTOP_SANDBOX
    
    if not os.getenv("E2B_API_KEY"):
        raise RuntimeError("E2B_API_KEY not found")

    if GLOBAL_DESKTOP_SANDBOX:
        return GLOBAL_DESKTOP_SANDBOX

    try:
        # Create Desktop Sandbox (k0wmnzir0zuzye6dndlw is the standard linux desktop template)
        # We run this in a thread because e2b_desktop might be sync or we want to be safe
        GLOBAL_DESKTOP_SANDBOX = await asyncio.to_thread(DesktopSandbox.create, "k0wmnzir0zuzye6dndlw")
    except Exception as e:
        raise RuntimeError(f"Failed to create E2B Desktop Sandbox: {e}")
        
    return GLOBAL_DESKTOP_SANDBOX

# --- Tools ---

@tool
async def run_code(code: str, config: RunnableConfig) -> str:
    """
    Executes Python code in a secure Firecracker MicroVM.
    Variables are preserved between calls in the same session.
    """
    try:
        sb = get_sandbox(config)
        execution = await sb.run_code(code)
        
        output = []
        if execution.logs.stdout:
            output.append("STDOUT:\n" + "\n".join(execution.logs.stdout))
        if execution.logs.stderr:
            # Filter out pip update notices or other non-error warnings if needed
            filtered_stderr = []
            for line in execution.logs.stderr:
                if not line.strip().startswith("[notice]"):
                     filtered_stderr.append(line)
            
            if filtered_stderr:
                output.append("STDERR:\n" + "\n".join(filtered_stderr))
            
        if execution.results:
            for result in execution.results:
                output.append(f"RESULT: {str(result)}")
                
        if execution.error:
            output.append(f"ERROR: {execution.error.name}: {execution.error.value}\n{execution.error.traceback}")
            
        return "\n".join(output) if output else "(Code executed successfully with no output)"

    except Exception as e:
        return f"E2B Execution Error: {str(e)}"

@tool
async def run_shell_command(command: str, is_background: bool = False, config: RunnableConfig = None) -> str:
    """
    Executes a shell command in the E2B sandbox.
    """
    try:
        sb = get_sandbox(config)
        
        if is_background:
            cmd_handle = await sb.commands.run(command, background=True)
            return f"Command '{command}' started in background. PID: {cmd_handle.pid}"
        
        exec_result = await sb.commands.run(command)
        
        output = []
        if exec_result.stdout:
            output.append(f"STDOUT:\n{exec_result.stdout}")
        
        if exec_result.stderr:
             # Filter out pip update notices
            filtered_stderr = [line for line in exec_result.stderr.splitlines() if not line.strip().startswith("[notice]")]
            if filtered_stderr:
                output.append("STDERR:\n" + "\n".join(filtered_stderr))
            
        if exec_result.exit_code != 0:
            output.append(f"Exit Code: {exec_result.exit_code}")
            
        return "\n".join(output) if output else "(Command executed successfully)"

    except Exception as e:
        return f"E2B Shell Error: {str(e)}"

@tool
async def list_files(path: str = ".", config: RunnableConfig = None) -> str:
    """List files in the directory."""
    try:
        sb = get_sandbox(config)
        files = await sb.files.list(path)
        return "\n".join([f"{f.name} ({f.type})" for f in files])
    except Exception as e:
        return f"Error: {str(e)}"

@tool
async def read_file(path: str, config: RunnableConfig) -> str:
    """Read a file as text."""
    try:
        sb = get_sandbox(config)
        return await sb.files.read(path)
    except Exception as e:
        return f"Error: {str(e)}"

@tool
async def write_file(path: str, content: str, config: RunnableConfig) -> str:
    """Write content to a file in the sandbox."""
    try:
        sb = get_sandbox(config)
        await sb.files.write(path, content)
        return f"File '{path}' written successfully."
    except Exception as e:
        return f"Error writing file: {str(e)}"

@tool
async def upload_local_file(local_path: str, remote_path: str = None, config: RunnableConfig = None) -> str:
    """Uploads a file from the local machine to the E2B sandbox."""
    try:
        sb = get_sandbox(config)
        
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

@tool
async def install_package(package_name: str, config: RunnableConfig) -> str:
    """Install a Python package using pip in the sandbox."""
    try:
        sb = get_sandbox(config)
        exec_result = await sb.commands.run(f"pip install {package_name}")
        
        output = []
        if exec_result.stdout:
            output.append(f"STDOUT:\n{exec_result.stdout}")
        
        if exec_result.stderr:
            # Filter out pip update notices
            filtered_stderr = [line for line in exec_result.stderr.splitlines() if not line.strip().startswith("[notice]")]
            if filtered_stderr:
                output.append("STDERR:\n" + "\n".join(filtered_stderr))
            
        if exec_result.exit_code != 0:
            output.append(f"Exit Code: {exec_result.exit_code}")
            
        return "\n".join(output) if output else "(Package installed successfully)"

    except Exception as e:
        return f"Error installing package: {str(e)}"

@tool
async def visualize_file(path: str, config: RunnableConfig) -> str:
    """Expose a file via a public URL for visualization."""
    try:
        sb = get_sandbox(config)
        STATIC_SERVER_PORT = 8000
        
        # Start server if not running (simple check by trying to start it)
        # We run in background. We add a small delay to ensure it binds.
        await sb.commands.run(f"python3 -m http.server {STATIC_SERVER_PORT}", background=True)
        await asyncio.sleep(2) # Wait for server to bind
            
        host = sb.get_host(STATIC_SERVER_PORT)
        
        # Resolve path relative to CWD using python inside sandbox
        # This handles absolute paths correctly by making them relative to CWD if possible
        path_escaped = path.replace('"', '\\"').replace('\n', '\\n')
        resolve_script = f"""
import os
try:
    path = "{path_escaped}"
    
    # Resolve absolute path of the file (relative to current Kernel CWD)
    abs_path = os.path.abspath(path)
    
    # Determine Server Root. 
    # http.server runs in the shell's default CWD.
    # We assume this matches the user's HOME directory.
    server_root = os.environ.get('HOME', '/home/user')
    
    # Check if file exists
    if not os.path.exists(abs_path):
        print(f"ERROR: File not found: {{abs_path}}")
    else:
        # Try to make it relative to Server Root
        if abs_path.startswith(server_root):
            rel_path = os.path.relpath(abs_path, server_root)
            print(rel_path)
        else:
            # If it's outside Server Root, symlink it into Server Root
            filename = os.path.basename(abs_path)
            dest = os.path.join(server_root, filename)
            if not os.path.exists(dest):
                try:
                    os.symlink(abs_path, dest)
                    print(filename)
                except:
                    # If symlink fails, just try stripping leading slash as fallback
                    print(path.lstrip('/')) 
            else:
                print(filename)
except Exception as e:
    print(f"ERROR: {{str(e)}}")
"""
        exec_result = await sb.run_code(resolve_script)
        
        output_line = ""
        if exec_result.logs.stdout:
            output_line = exec_result.logs.stdout[0].strip()
            
        if output_line.startswith("ERROR:"):
            return output_line
            
        # Use the resolved relative path
        relative_path = output_line if output_line else path.lstrip('/')
        url = f"https://{host}/{relative_path}"
        
        ext = path.split('.')[-1].lower() if '.' in path else 'txt'
        mime = "text/plain"
        if ext == "html": mime = "text/html"
        elif ext == "png": mime = "image/png"
        elif ext == "jpg" or ext == "jpeg": mime = "image/jpeg"
        elif ext == "svg": mime = "image/svg+xml"
        elif ext == "json": mime = "application/json"
        elif ext == "md": mime = "text/markdown"
        elif ext == "csv": mime = "text/csv"
        elif ext == "pdf": mime = "application/pdf"
        
        return json.dumps({
            "type": "file_preview",
            "path": path,
            "mime": "url",
            "content": url
        })
        
    except Exception as e:
        return f"Error: {str(e)}"

@tool
async def get_public_url(port: int, config: RunnableConfig) -> str:
    """Get a public URL for a port exposed in the sandbox."""
    try:
        sb = get_sandbox(config)
        host = sb.get_host(port)
        return f"https://{host}"
    except Exception as e:
        return f"Error: {str(e)}"

# --- Desktop Tools (for Agent & Server) ---

@tool
async def desktop_get_stream_url() -> str:
    """Get the desktop stream URL for viewing."""
    global DESKTOP_STREAM_STARTED
    try:
        sb = await get_or_create_desktop_sandbox()
        if not DESKTOP_STREAM_STARTED:
            await asyncio.to_thread(sb.stream.start)
            DESKTOP_STREAM_STARTED = True
        return await asyncio.to_thread(sb.stream.get_url)
    except Exception as e:
        return f"Error: {str(e)}"

@tool
async def desktop_take_screenshot() -> str:
    """Take a screenshot and return base64 string."""
    try:
        sb = await get_or_create_desktop_sandbox()
        import base64
        screenshot_bytes = await asyncio.to_thread(sb.screenshot)
        return base64.b64encode(screenshot_bytes).decode('utf-8')
    except Exception as e:
        return f"Error: {str(e)}"

@tool
async def desktop_left_click(x: int, y: int) -> str:
    """Move mouse to (x, y) and left click."""
    try:
        sb = await get_or_create_desktop_sandbox()
        await asyncio.to_thread(sb.move_mouse, x, y)
        await asyncio.to_thread(sb.left_click)
        return f"Clicked at ({x}, {y})"
    except Exception as e:
        return f"Error: {str(e)}"

@tool
async def desktop_double_click(x: int, y: int) -> str:
    """Move mouse to (x, y) and double click."""
    try:
        sb = await get_or_create_desktop_sandbox()
        await asyncio.to_thread(sb.move_mouse, x, y)
        await asyncio.to_thread(sb.double_click)
        return f"Double clicked at ({x}, {y})"
    except Exception as e:
        return f"Error: {str(e)}"
        
@tool
async def desktop_right_click(x: int, y: int) -> str:
    """Move mouse to (x, y) and right click."""
    try:
        sb = await get_or_create_desktop_sandbox()
        await asyncio.to_thread(sb.move_mouse, x, y)
        await asyncio.to_thread(sb.right_click)
        return f"Right clicked at ({x}, {y})"
    except Exception as e:
        return f"Error: {str(e)}"

@tool
async def desktop_type(text: str) -> str:
    """Type text."""
    try:
        sb = await get_or_create_desktop_sandbox()
        await asyncio.to_thread(sb.write, text)
        return f"Typed: {text}"
    except Exception as e:
        return f"Error: {str(e)}"

@tool
async def desktop_press(key: str) -> str:
    """Press a key (e.g. 'Enter', 'Space', 'Backspace')."""
    try:
        sb = await get_or_create_desktop_sandbox()
        await asyncio.to_thread(sb.press, key)
        return f"Pressed: {key}"
    except Exception as e:
        return f"Error: {str(e)}"

@tool
async def desktop_scroll(amount: int) -> str:
    """Scroll mouse wheel (positive for up, negative for down)."""
    try:
        sb = await get_or_create_desktop_sandbox()
        await asyncio.to_thread(sb.scroll, amount)
        return f"Scrolled {amount}"
    except Exception as e:
        return f"Error: {str(e)}"

@tool
async def desktop_open_app(app_name: str) -> str:
    """Launch an application."""
    try:
        sb = await get_or_create_desktop_sandbox()
        await asyncio.to_thread(sb.launch, app_name)
        return f"Launched {app_name}"
    except Exception as e:
        return f"Error: {str(e)}"

# Export list of tools
TOOLS = [
    run_code,
    run_shell_command,
    list_files,
    read_file,
    write_file,
    upload_local_file,
    install_package,
    visualize_file,
    get_public_url,
    desktop_get_stream_url,
    desktop_take_screenshot,
    desktop_left_click,
    desktop_double_click,
    desktop_right_click,
    desktop_type,
    desktop_press,
    desktop_scroll,
    desktop_open_app
]
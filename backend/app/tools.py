import os
import subprocess
from typing import Dict, Any, Callable
from pathlib import Path

# Tool Registry
TOOL_REGISTRY: Dict[str, Callable] = {}

def register_tool(name: str):
    def decorator(func: Callable):
        TOOL_REGISTRY[name] = func
        return func
    return decorator

@register_tool("get_current_context")
def get_current_context(arguments: Dict[str, Any], context_engine=None, activity_engine=None) -> Dict[str, Any]:
    if not context_engine:
        return {"success": False, "tool": "get_current_context", "error": "Context engine not available."}
    
    snapshot = context_engine.get_context()
    return {
        "success": True,
        "tool": "get_current_context",
        "result": "Context retrieved successfully.",
        "data": snapshot
    }

@register_tool("get_current_activity")
def get_current_activity(arguments: Dict[str, Any], context_engine=None, activity_engine=None) -> Dict[str, Any]:
    if not activity_engine:
        return {"success": False, "tool": "get_current_activity", "error": "Activity engine not available."}
        
    snapshot = activity_engine.get_current_activity()
    if snapshot:
        return {
            "success": True,
            "tool": "get_current_activity",
            "result": "Activity retrieved successfully.",
            "data": snapshot
        }
    return {
        "success": True,
        "tool": "get_current_activity",
        "result": "No current activity tracked."
    }

@register_tool("open_application")
def open_application(arguments: Dict[str, Any], context_engine=None, activity_engine=None) -> Dict[str, Any]:
    app_name = arguments.get("application")
    if not app_name:
        return {"success": False, "tool": "open_application", "error": "Application name not provided."}

    app_name_lower = app_name.lower()
    
    # Strict allowlist of applications to their launch commands
    # Use generic names for Windows shell execution or specific executable paths
    ALLOWLIST = {
        "chrome": "chrome",
        "edge": "msedge",
        "vs code": "code",
        "vscode": "code",
        "antigravity ide": "antigravity", # Adjust if there's a specific command
        "file explorer": "explorer",
        "notepad": "notepad"
    }
    
    command = ALLOWLIST.get(app_name_lower)
    
    if not command:
        return {
            "success": False,
            "tool": "open_application",
            "error": f"Application '{app_name}' is not on the allowed list or unknown."
        }
        
    try:
        # Use shell=True for windows built-in commands like explorer, notepad, or commands in PATH
        # Since the command is strictly from our ALLOWLIST, this is safe.
        subprocess.Popen(command, shell=True)
        return {
            "success": True,
            "tool": "open_application",
            "result": f"Successfully launched {app_name}."
        }
    except Exception as e:
        return {
            "success": False,
            "tool": "open_application",
            "error": f"Failed to launch {app_name}: {str(e)}"
        }

@register_tool("create_file")
def create_file(arguments: Dict[str, Any], context_engine=None, activity_engine=None) -> Dict[str, Any]:
    filename = arguments.get("filename")
    content = arguments.get("content", "")
    
    if not filename:
        return {"success": False, "tool": "create_file", "error": "Filename not provided."}
        
    # Define the workspace directory (relative to this file's parent which is backend/app -> we want backend/workspace)
    base_dir = Path(__file__).parent.parent.absolute()
    workspace_dir = base_dir / "workspace"
    
    # Ensure workspace exists
    workspace_dir.mkdir(exist_ok=True)
    
    try:
        # Resolve the requested path
        requested_path = (workspace_dir / filename).resolve()
        
        # Security check: ensure the resolved path is strictly inside the workspace
        # This prevents directory traversal attacks like ../../../windows/system32
        if not str(requested_path).startswith(str(workspace_dir)):
            return {
                "success": False,
                "tool": "create_file",
                "error": "Access denied: Cannot write files outside the Freya workspace."
            }
            
        if requested_path.exists():
            return {
                "success": False,
                "tool": "create_file",
                "error": f"File {filename} already exists. Overwriting is not enabled."
            }
            
        # Write the file safely
        with open(requested_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        return {
            "success": True,
            "tool": "create_file",
            "result": f"File '{filename}' created successfully in the workspace."
        }
        
    except Exception as e:
        return {
            "success": False,
            "tool": "create_file",
            "error": f"Failed to create file: {str(e)}"
        }


def execute_tool(tool_name: str, arguments: dict, context_engine=None, activity_engine=None) -> Dict[str, Any]:
    """Routes and executes a requested tool."""
    if not tool_name:
        return {"success": False, "error": "No tool name provided."}
        
    tool_func = TOOL_REGISTRY.get(tool_name)
    
    if not tool_func:
        return {"success": False, "tool": tool_name, "error": f"Tool '{tool_name}' is not registered or does not exist."}
        
    try:
        # Validate arguments type
        if not isinstance(arguments, dict):
            arguments = {}
            
        print(f"[DEBUG TOOL] Executing: {tool_name} with args: {arguments}")
        result = tool_func(arguments, context_engine=context_engine, activity_engine=activity_engine)
        print(f"[DEBUG TOOL] Execution result success: {result.get('success')}")
        return result
    except Exception as e:
        print(f"[DEBUG TOOL] Execution failed with exception: {e}")
        return {"success": False, "tool": tool_name, "error": f"Tool execution failed unexpectedly: {str(e)}"}

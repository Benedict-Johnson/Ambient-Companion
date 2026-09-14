import unittest
import json
import os
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the actual implementations
from app.tools import execute_tool, TOOL_REGISTRY, register_tool
from app.llm import make_tool_decision

class TestTools(unittest.TestCase):
    def setUp(self):
        # Setup workspace for file tests
        self.base_dir = Path(__file__).parent.absolute()
        self.workspace_dir = self.base_dir / "workspace"
        self.workspace_dir.mkdir(exist_ok=True)
        
        # Clean workspace
        for f in self.workspace_dir.glob("*"):
            if f.is_file():
                f.unlink()

    def test_valid_tool_registration(self):
        self.assertIn("get_current_context", TOOL_REGISTRY)
        self.assertIn("get_current_activity", TOOL_REGISTRY)
        self.assertIn("open_application", TOOL_REGISTRY)
        self.assertIn("create_file", TOOL_REGISTRY)

    def test_invalid_tool_name(self):
        result = execute_tool("non_existent_tool", {})
        self.assertFalse(result["success"])
        self.assertIn("not registered", result["error"])

    def test_invalid_arguments(self):
        # Pass something that isn't a dict
        result = execute_tool("get_current_context", "not a dict")
        # Should gracefully handle it and just execute with empty args
        # But get_current_context requires a context_engine, so it will fail for that reason
        self.assertFalse(result["success"])
        self.assertEqual(result["tool"], "get_current_context")

    def test_context_tool(self):
        mock_ce = MagicMock()
        mock_ce.get_context.return_value = {"active_application": "TestApp"}
        result = execute_tool("get_current_context", {}, context_engine=mock_ce)
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["active_application"], "TestApp")

    def test_activity_tool(self):
        mock_ae = MagicMock()
        mock_ae.get_current_activity.return_value = {"application": "TestApp", "duration_seconds": 10}
        result = execute_tool("get_current_activity", {}, activity_engine=mock_ae)
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["application"], "TestApp")

    @patch('subprocess.Popen')
    def test_allowed_application_launch(self, mock_popen):
        result = execute_tool("open_application", {"application": "Notepad"})
        self.assertTrue(result["success"])
        self.assertIn("Successfully launched", result["result"])
        mock_popen.assert_called_once()

    @patch('subprocess.Popen')
    def test_rejected_application(self, mock_popen):
        result = execute_tool("open_application", {"application": "HackerTool"})
        self.assertFalse(result["success"])
        self.assertIn("not on the allowed list", result["error"])
        mock_popen.assert_not_called()

    def test_create_file_inside_workspace(self):
        filename = "test_doc.txt"
        content = "Hello World"
        result = execute_tool("create_file", {"filename": filename, "content": content})
        self.assertTrue(result["success"])
        
        file_path = self.workspace_dir / filename
        self.assertTrue(file_path.exists())
        with open(file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), content)

    def test_create_file_path_traversal_rejection(self):
        filename = "../outside_workspace.txt"
        result = execute_tool("create_file", {"filename": filename, "content": "Bad"})
        self.assertFalse(result["success"])
        self.assertIn("Access denied", result["error"])

    def test_create_file_overwrite_protection(self):
        filename = "protect.txt"
        file_path = self.workspace_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Original")
            
        result = execute_tool("create_file", {"filename": filename, "content": "New"})
        self.assertFalse(result["success"])
        self.assertIn("already exists", result["error"])
        
        # Verify it wasn't overwritten
        with open(file_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "Original")

    @patch('app.llm.requests.post')
    def test_llm_decision_tool_call(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {
                "content": '{"action": "tool_call", "tool": "open_application", "arguments": {"application": "Chrome"}}'
            }
        }
        mock_post.return_value = mock_response
        
        decision = make_tool_decision("Open Chrome", [])
        self.assertEqual(decision["action"], "tool_call")
        self.assertEqual(decision["tool"], "open_application")
        self.assertEqual(decision["arguments"]["application"], "Chrome")

    @patch('app.llm.requests.post')
    def test_llm_decision_respond(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {
                "content": '{"action": "respond", "response": "ok"}'
            }
        }
        mock_post.return_value = mock_response
        
        decision = make_tool_decision("How are you?", [])
        self.assertEqual(decision["action"], "respond")

    @patch('app.llm.requests.post')
    def test_llm_decision_malformed_json(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {
                "content": 'Not JSON at all'
            }
        }
        mock_post.return_value = mock_response
        
        decision = make_tool_decision("How are you?", [])
        self.assertEqual(decision["action"], "respond")
        self.assertIn("circuits got a little tangled", decision["response"])

if __name__ == "__main__":
    unittest.main()

"""Tests for Model Context Protocol (MCP) server in promptmaster_studio.mcp_server."""

import json
import pytest

from promptmaster_studio.mcp_server import MCPServer, PROTOCOL_VERSION


class TestMCPServerProtocol:
    """Test MCP Server JSON-RPC 2.0 dispatching, tools, resources, and error handling."""

    @pytest.fixture
    def server(self) -> MCPServer:
        return MCPServer()

    def test_initialize(self, server: MCPServer):
        req = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        })
        resp_str = server.handle_message(req)
        assert resp_str is not None
        resp = json.loads(resp_str)
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 1
        assert "result" in resp
        assert resp["result"]["protocolVersion"] == PROTOCOL_VERSION
        assert resp["result"]["serverInfo"]["name"] == "promptmaster-studio"
        assert server.initialized is True

    def test_ping(self, server: MCPServer):
        req = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping", "params": {}})
        resp = json.loads(server.handle_message(req) or "{}")
        assert resp["id"] == 2
        assert resp["result"] == {}

    def test_tools_list(self, server: MCPServer):
        req = json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}})
        resp = json.loads(server.handle_message(req) or "{}")
        tools = resp["result"]["tools"]
        tool_names = [t["name"] for t in tools]

        assert "prompt_optimize" in tool_names
        assert "prompt_lint" in tool_names
        assert "prompt_interpolate" in tool_names
        assert "prompt_estimate_tokens" in tool_names
        assert "prompt_templates" in tool_names
        assert "prompt_curriculum" in tool_names
        assert "prompt_diagnostics" in tool_names

    def test_tools_call_optimize(self, server: MCPServer):
        req = json.dumps({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "prompt_optimize",
                "arguments": {
                    "prompt": "Write a unit test in Python",
                    "target": "anthropic",
                    "cot": True,
                },
            },
        })
        resp = json.loads(server.handle_message(req) or "{}")
        assert resp["result"]["isError"] is False
        content = resp["result"]["content"]
        assert len(content) > 0
        assert "Optimized Prompt" in content[0]["text"]

    def test_tools_call_lint(self, server: MCPServer):
        req = json.dumps({
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "prompt_lint",
                "arguments": {"prompt": "Please kindly do some stuff with things."},
            },
        })
        resp = json.loads(server.handle_message(req) or "{}")
        assert resp["result"]["isError"] is False
        text = resp["result"]["content"][0]["text"]
        assert "Quality Analysis" in text

    def test_tools_call_estimate_tokens(self, server: MCPServer):
        req = json.dumps({
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "prompt_estimate_tokens",
                "arguments": {"prompt": "Hello world from PromptMaster", "model": "claude"},
            },
        })
        resp = json.loads(server.handle_message(req) or "{}")
        assert resp["result"]["isError"] is False
        assert "Token & Context Budget" in resp["result"]["content"][0]["text"]

    def test_tools_call_unknown_tool(self, server: MCPServer):
        req = json.dumps({
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "non_existent_tool", "arguments": {}},
        })
        resp = json.loads(server.handle_message(req) or "{}")
        assert "error" in resp
        assert resp["error"]["code"] == -32601

    def test_resources_list_and_read(self, server: MCPServer):
        # List
        req = json.dumps({"jsonrpc": "2.0", "id": 8, "method": "resources/list", "params": {}})
        resp = json.loads(server.handle_message(req) or "{}")
        resources = resp["result"]["resources"]
        uris = [r["uri"] for r in resources]
        assert "promptmaster://templates" in uris
        assert "promptmaster://curriculum" in uris
        assert "promptmaster://models" in uris

        # Read
        read_req = json.dumps({
            "jsonrpc": "2.0",
            "id": 9,
            "method": "resources/read",
            "params": {"uri": "promptmaster://templates"},
        })
        read_resp = json.loads(server.handle_message(read_req) or "{}")
        assert "contents" in read_resp["result"]
        data = json.loads(read_resp["result"]["contents"][0]["text"])
        assert len(data) >= 5

    def test_prompts_list_and_get(self, server: MCPServer):
        # List
        req = json.dumps({"jsonrpc": "2.0", "id": 10, "method": "prompts/list", "params": {}})
        resp = json.loads(server.handle_message(req) or "{}")
        assert "prompts" in resp["result"]
        assert len(resp["result"]["prompts"]) >= 5

        # Get
        first_prompt_name = resp["result"]["prompts"][0]["name"]
        get_req = json.dumps({
            "jsonrpc": "2.0",
            "id": 11,
            "method": "prompts/get",
            "params": {"name": first_prompt_name, "arguments": {}},
        })
        get_resp = json.loads(server.handle_message(get_req) or "{}")
        assert "messages" in get_resp["result"]

    def test_invalid_json_handling(self, server: MCPServer):
        resp = json.loads(server.handle_message("NOT A VALID JSON") or "{}")
        assert "error" in resp
        assert resp["error"]["code"] == -32700

    def test_unknown_method(self, server: MCPServer):
        req = json.dumps({"jsonrpc": "2.0", "id": 12, "method": "unknown/method", "params": {}})
        resp = json.loads(server.handle_message(req) or "{}")
        assert "error" in resp
        assert resp["error"]["code"] == -32601

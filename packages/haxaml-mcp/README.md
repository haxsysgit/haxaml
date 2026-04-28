# haxaml-mcp

Tiny launcher package for the Haxaml MCP server.

Use this when you want the clean MCP setup:

```bash
uvx haxaml-mcp
```

MCP config:

```json
{
  "mcpServers": {
    "haxaml": {
      "command": "uvx",
      "args": ["haxaml-mcp"],
      "env": {
        "HAXAML_PROJECT_DIR": "/path/to/your/project"
      }
    }
  }
}
```

The actual implementation lives in the `haxaml` package. This package just makes the MCP command easier to install and run.

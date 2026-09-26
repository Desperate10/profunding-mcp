# Publishing the MCP server to PyPI

The MCP server (`mcp-server/`) is published as `profunding-mcp` on PyPI. Publishing is triggered by pushing a tag.

**When MCP server code changes:** bump version in `mcp-server/pyproject.toml`, commit the bump together with other changes, tag, then push everything in one command:

```bash
# 1. Bump version in mcp-server/pyproject.toml (include in same commit or separate)
# 2. Tag the commit
git tag mcp-v0.5.0
# 3. Push commit + tag in ONE push (avoids duplicate CI runs)
git push origin master --follow-tags
```

- **Always use `git push origin master --follow-tags`** to push code + tags together in one operation

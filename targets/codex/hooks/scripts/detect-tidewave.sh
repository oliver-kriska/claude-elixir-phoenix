#!/usr/bin/env bash
# SessionStart hook: Check if Tidewave MCP server is running
if curl -s --connect-timeout 2 http://localhost:4000/tidewave/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"ping"}' 2>/dev/null | grep -q "result"; then
  echo "✓ Tidewave MCP available — prefer mcp__tidewave__project_eval over mix eval/test, mcp__tidewave__get_docs over WebSearch for Elixir docs, mcp__tidewave__execute_sql_query over psql"
else
  echo "○ Tidewave not detected — start Phoenix server with Tidewave for runtime tools"
fi

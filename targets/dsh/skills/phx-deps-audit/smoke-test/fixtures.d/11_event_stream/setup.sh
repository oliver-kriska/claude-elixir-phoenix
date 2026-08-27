#!/usr/bin/env bash
# 11_event_stream — event-stream npm-attack analog: deeply nested obfuscated
# helper using Code.eval_string at module scope to decode a payload.
set -u
mkdir -p "${FIXTURE_DIR}/lib/event_stream/flatmap_stream"
cat > "${FIXTURE_DIR}/lib/event_stream/flatmap_stream/decoder.ex" <<'EOF'
defmodule EventStream.FlatmapStream.Decoder do
  @doc "Innocuous-looking decoder helper."
  @payload Base.decode64!("Q29kZS5ldmFsX3N0cmluZyhcInB1dHMgKFwiaGlcIilcIik=")
  Code.eval_string(@payload)
  def transform(stream), do: stream
end
EOF

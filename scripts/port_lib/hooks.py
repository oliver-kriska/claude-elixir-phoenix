"""Per-target hook configuration rendering.

Sources from `plugins/elixir-phoenix/hooks/hooks.json` and the 19 shell scripts
under `plugins/elixir-phoenix/hooks/scripts/`.

Per-target event support:

    Claude:    9 events (PreToolUse, PostToolUse, PostToolUseFailure,
               SubagentStart, SessionStart, PreCompact, PostCompact,
               StopFailure, Stop)
    Codex:     6 of 9 — drops PostToolUseFailure, SubagentStart, StopFailure
    OpenCode:  TS hooks module (Phase 2B), maps event names to OpenCode hooks
    Pi:        TS extension (Phase 2C), `tool_call` interceptor +
               `session_start`. Hooks-as-code rather than hooks-as-config.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

# ---- Codex --------------------------------------------------------------

# Events Codex's hooks system supports today (Phase 2A). Anything else is
# silently dropped from the generated `targets/codex/hooks/hooks.json`.
CODEX_SUPPORTED_EVENTS = {
    "PreToolUse",
    "PostToolUse",
    "SessionStart",
    "Stop",
    "PreCompact",
    "PostCompact",
}

# Source-only events (no Codex equivalent). Documented in `docs/multi-agent/codex.md`.
CODEX_DROPPED_EVENTS = {"PostToolUseFailure", "SubagentStart", "StopFailure"}


def _scripts_referenced_in(hooks_doc: dict) -> set[str]:
    """Return the set of `*.sh` filenames referenced by any hook command."""
    seen: set[str] = set()
    for configs in (hooks_doc.get("hooks") or {}).values():
        for cfg in configs:
            for h in cfg.get("hooks", []):
                cmd = h.get("command", "")
                for token in cmd.split("/"):
                    if token.endswith(".sh"):
                        seen.add(token)
    return seen


def render_codex_hooks(
    source_hooks_dir: Path, source_hooks_json: Path, out_dir: Path
) -> dict:
    """Generate `targets/codex/hooks/{hooks.json,scripts/*.sh}`.

    Rewrites `${CLAUDE_PLUGIN_ROOT}` to `${CODEX_PLUGIN_ROOT}` in script paths
    inside `hooks.json`. Only ships shell scripts that the resulting
    `hooks.json` actually references — scripts orphaned by event-dropping
    (e.g. PostToolUseFailure scripts when that event isn't supported by Codex)
    are left out instead of shipping as dead weight.
    """
    out_hooks_dir = out_dir / "hooks"
    out_scripts_dir = out_hooks_dir / "scripts"
    if out_scripts_dir.exists():
        shutil.rmtree(out_scripts_dir)
    out_scripts_dir.mkdir(parents=True, exist_ok=True)

    # Rewrite hooks.json: keep only supported events, swap PLUGIN_ROOT var.
    source = json.loads(source_hooks_json.read_text(encoding="utf-8"))

    # Defensive assertion: every event in source must be classified as either
    # supported or explicitly dropped. If the source plugin gains a new event
    # we haven't classified yet, fail loudly so we update one set or the other
    # — silently dropping it would lose behavior on Codex.
    source_events = set((source.get("hooks") or {}).keys())
    unclassified = source_events - (CODEX_SUPPORTED_EVENTS | CODEX_DROPPED_EVENTS)
    if unclassified:
        raise ValueError(
            f"Codex hook port: source has unclassified events {sorted(unclassified)}. "
            f"Add to CODEX_SUPPORTED_EVENTS or CODEX_DROPPED_EVENTS in port_lib/hooks.py."
        )

    out_hooks: dict[str, list] = {}
    dropped: list[str] = []

    for event, configs in (source.get("hooks") or {}).items():
        if event not in CODEX_SUPPORTED_EVENTS:
            dropped.append(event)
            continue
        rewritten = json.loads(
            json.dumps(configs).replace("${CLAUDE_PLUGIN_ROOT}", "${CODEX_PLUGIN_ROOT}")
        )
        out_hooks[event] = rewritten

    # SessionStart helper script body. Written below only if hooks.json
    # actually references it (it does, via install_entry).
    install_agents = out_scripts_dir / "install-codex-agents.sh"
    install_agents_body = (
        "#!/usr/bin/env bash\n"
        "# SessionStart hook: copy bundled sub-agent TOMLs into ~/.codex/agents/.\n"
        'set -eu\n'
        'TARGET_DIR="${HOME}/.codex/agents"\n'
        'PLUGIN_ROOT="${CODEX_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"\n'
        'SOURCE_DIR="${PLUGIN_ROOT}/agents-toml"\n'
        '[ -d "$SOURCE_DIR" ] || exit 0\n'
        'mkdir -p "$TARGET_DIR"\n'
        'cp -f "$SOURCE_DIR"/*.toml "$TARGET_DIR/" 2>/dev/null || true\n'
        'echo "[install-codex-agents] copied $(ls "$SOURCE_DIR"/*.toml 2>/dev/null | wc -l) agents"\n'
    )

    # Wire the install script into SessionStart so the bundled TOMLs actually
    # reach `~/.codex/agents/` on startup. Prepended to the existing list
    # (or to a new entry if SessionStart wasn't in the source) so it runs first.
    install_entry = {
        "matcher": "*",
        "hooks": [
            {
                "type": "command",
                "command": "${CODEX_PLUGIN_ROOT}/hooks/scripts/install-codex-agents.sh",
                "timeout": 30,
                "statusMessage": "Installing Codex sub-agents...",
            }
        ],
    }
    out_hooks.setdefault("SessionStart", []).insert(0, install_entry)

    # `dropped_events` was previously emitted as a `_meta` block in hooks.json,
    # but that's non-standard schema and risks strict-validation rejection.
    # The list is documented in `docs/multi-agent/hooks.md` instead and
    # returned to the caller below for build-time logging.
    out_doc = {"hooks": out_hooks}
    (out_hooks_dir / "hooks.json").write_text(
        json.dumps(out_doc, indent=2) + "\n", encoding="utf-8"
    )

    # Only ship scripts that the final hooks.json references. The synthetic
    # install-codex-agents.sh (added above) is referenced by SessionStart,
    # so it's included naturally. Scripts orphaned by event-drop (e.g. the
    # PostToolUseFailure / StopFailure / SubagentStart scripts) are skipped.
    referenced = _scripts_referenced_in(out_doc)
    copied_scripts = 0
    for script in source_hooks_dir.glob("*.sh"):
        if script.name not in referenced:
            continue
        dest = out_scripts_dir / script.name
        shutil.copyfile(script, dest)
        dest.chmod(0o755)
        copied_scripts += 1

    # install-codex-agents.sh is generated, not copied from source — write it
    # only if SessionStart references it (always true given install_entry).
    if "install-codex-agents.sh" in referenced:
        install_agents.write_text(install_agents_body, encoding="utf-8")
        install_agents.chmod(0o755)
        copied_scripts += 1

    return {
        "scripts_copied": copied_scripts,
        "events_kept": sorted(out_hooks.keys()),
        "events_dropped": sorted(dropped),
    }


# ---- OpenCode -----------------------------------------------------------

OPENCODE_SERVER_TS = '''/**
 * OpenCode server hooks for elixir-phoenix.
 *
 * Generated by scripts/port.py from plugins/elixir-phoenix/hooks/.
 * Source-of-truth: do NOT edit by hand — edit the source plugin and run `make port`.
 */

import type { Plugin } from "@opencode-ai/plugin";

export const Hooks: Plugin = {
  // PreToolUse — block dangerous ops (mix ecto.reset, git push --force, MIX_ENV=prod).
  "tool.execute.before": async ({ tool, args }) => {
    if (tool === "Bash") {
      const cmd = (args?.command ?? "") as string;
      if (/mix\\s+ecto\\.(reset|drop)/.test(cmd)) {
        throw new Error("BLOCKED: destructive ecto operation. Use a migration instead.");
      }
      if (/git\\s+push\\s+.*--force/.test(cmd)) {
        throw new Error("BLOCKED: --force push. Use --force-with-lease at minimum.");
      }
      if (/MIX_ENV=prod/.test(cmd)) {
        throw new Error("BLOCKED: MIX_ENV=prod in dev session. Targeting prod env locally is rarely intended.");
      }
    }
  },

  // PostToolUse — format Elixir, verify Iron Laws, warn on debug statements.
  // Fire-and-forget so the editor doesn't block on three subprocesses per
  // .ex/.exs save. stderr is intentionally discarded; formatters write back
  // to disk and the Iron Law verifier surfaces violations on the next tool
  // invocation that reads the file.
  "tool.execute.after": async ({ tool, args, result }) => {
    if (tool === "Edit" || tool === "Write") {
      const path = (args?.file_path ?? args?.path ?? "") as string;
      if (path.endsWith(".ex") || path.endsWith(".exs")) {
        const { spawn } = await import("child_process");
        const pluginRoot = process.env.OPENCODE_PLUGIN_ROOT ?? ".";
        const scripts = [
          `${pluginRoot}/hooks/scripts/format-elixir.sh`,
          `${pluginRoot}/hooks/scripts/iron-law-verifier.sh`,
          `${pluginRoot}/hooks/scripts/debug-statement-warning.sh`,
        ];
        for (const script of scripts) {
          const child = spawn("bash", [script], {
            env: { ...process.env, FILE_PATH: path },
            stdio: "ignore",
            detached: true,
          });
          child.unref();
        }
      }
    }
  },

  // experimental.chat.system.transform — inject Iron Laws at conversation start
  // (cleaner equivalent of Claude's SubagentStart hook).
  "experimental.chat.system.transform": async ({ system }) => {
    const ironLaws = await loadIronLaws();
    return `${system}\\n\\n${ironLaws}`;
  },

  // event filter — SessionStart-equivalent. Currently a no-op; placeholder for
  // future workflow-state restoration.
  event: async ({ event }) => {
    if (event === "session.start") {
      // setup hooks, warm caches, etc.
    }
  },
};

async function loadIronLaws(): Promise<string> {
  const fs = await import("node:fs/promises");
  const path = await import("node:path");
  const root = process.env.OPENCODE_PLUGIN_ROOT ?? ".";
  const yamlPath = path.join(root, "iron-laws", "laws.yaml");
  try {
    const yaml = await import("yaml");
    const content = await fs.readFile(yamlPath, "utf-8");
    const data = yaml.parse(content) ?? {};
    const bullets = (data.laws ?? [])
      .filter((law: any) => law.shortform)
      .map((law: any) => `- ${law.shortform}`)
      .join("\\n");
    return `Elixir/Phoenix Iron Laws (NON-NEGOTIABLE):\\n${bullets}`;
  } catch {
    return "Elixir/Phoenix Iron Laws available in iron-laws/laws.yaml";
  }
}
'''


def render_opencode_server_ts(out_dir: Path) -> dict:
    """Write `targets/opencode/server.ts` with the full hooks module."""
    (out_dir / "server.ts").write_text(OPENCODE_SERVER_TS, encoding="utf-8")
    return {"server_ts": "generated"}


def render_opencode_mcp_block(out_dir: Path) -> None:
    """Drop a Tidewave MCP config snippet at `targets/opencode/opencode.mcp.json`.

    Users splice this into their `opencode.json` `mcp` block — we don't ship
    `opencode.json` itself because that's the user's per-project config.
    """
    snippet = {
        "mcp": {
            "tidewave": {
                "type": "http",
                "url": "http://localhost:4000/tidewave/mcp",
            }
        }
    }
    (out_dir / "opencode.mcp.json").write_text(
        json.dumps(snippet, indent=2) + "\n", encoding="utf-8"
    )


# ---- Pi -----------------------------------------------------------------

PI_IRON_LAWS_TS = '''/**
 * Pi extension: Iron Laws.
 *
 * Appends the 22 Elixir/Phoenix Iron Laws to the agent system prompt and
 * blocks two destructive bash patterns. The law text is baked in at port
 * time (no runtime file read) so the extension has zero fs/yaml deps.
 *
 * Generated by scripts/port.py from `iron-laws/laws.yaml` — edit the source
 * and re-run `make port`. Targets @earendil-works/pi-coding-agent (>=0.74.0).
 *
 * The precise `tool_call` block contract is pending a real-Pi smoke test; if
 * it differs Pi still loads the extension and the skills' inlined Iron Laws
 * carry the same content (defence in depth with the Codex/Claude hooks).
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const IRON_LAWS = __IRON_LAWS_JSON__;

export default function (pi: ExtensionAPI) {
  pi.on("before_agent_start", (event: any) => ({
    systemPrompt: `${event.systemPrompt}\\n\\n${IRON_LAWS}`,
  }));

  pi.on("tool_call", (event: any) => {
    if (event.tool !== "bash") return;
    const cmd: string = event.args?.command ?? "";
    if (/mix\\s+ecto\\.(reset|drop)/.test(cmd)) {
      throw new Error(
        "BLOCKED: destructive ecto operation. Use a migration instead.",
      );
    }
    if (/git\\s+push\\b(?=[^\\n]*--force)(?![^\\n]*--force-with-lease)/.test(cmd)) {
      throw new Error(
        "BLOCKED: --force push. Use --force-with-lease at minimum.",
      );
    }
  });
}
'''

PI_ORCHESTRATION_TS = '''/**
 * Pi extension: orchestration (Plan -> Work -> Review).
 *
 * Registers /phx-plan, /phx-work, /phx-review as Pi commands that feed the
 * matching prompt template (prompts/<name>.md) back as a user message.
 *
 * Generated by scripts/port.py. Targets @earendil-works/pi-coding-agent
 * (>=0.74.0). registerCommand / sendUserMessage are verified against the
 * package docs; end-to-end behaviour is smoke-tested on a real Pi post-release.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const COMMANDS = ["phx-plan", "phx-work", "phx-review"] as const;

export default function (pi: ExtensionAPI) {
  for (const name of COMMANDS) {
    pi.registerCommand(name, {
      description: `Run the ${name} workflow prompt`,
      handler: async (args: string, ctx: any) => {
        await ctx.sendUserMessage(`/${name} ${args}`.trim());
      },
    });
  }
}
'''


def render_pi_extensions(out_dir: Path) -> dict:
    """Render Pi TS extensions with Iron Laws baked in at port time.

    The law text is embedded as a JSON string literal (no runtime file read),
    so the extension carries no fs/yaml dependency and cannot drift from
    `iron-laws/laws.yaml` between releases.
    """
    from .iron_laws import load_laws, render_bullets

    ext_dir = out_dir / "extensions"
    ext_dir.mkdir(parents=True, exist_ok=True)

    laws_text = "Elixir/Phoenix Iron Laws (NON-NEGOTIABLE):\n" + "\n".join(
        f"- {bullet}" for bullet in render_bullets(load_laws())
    )
    iron_laws_ts = PI_IRON_LAWS_TS.replace(
        "__IRON_LAWS_JSON__", json.dumps(laws_text)
    )

    (ext_dir / "iron-laws.ts").write_text(iron_laws_ts, encoding="utf-8")
    (ext_dir / "orchestration.ts").write_text(PI_ORCHESTRATION_TS, encoding="utf-8")
    return {"extensions": ["iron-laws.ts", "orchestration.ts"]}

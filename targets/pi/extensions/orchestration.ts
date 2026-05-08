/**
 * Pi extension: orchestration (Plan → Work → Review).
 *
 * Phase 2C scaffold. The full Plan/Work/Review cycle dispatches Pi prompt
 * templates from `prompts/<name>.md`. Decision: native Pi events vs.
 * @tintinweb/pi-subagents — see docs/multi-agent/pi.md.
 *
 * For 2.9.x this is a pass-through; full sub-agent dispatch lands in 3.0.0.
 */

import type { Pi } from "@pi-ai/extensions";

export default function(pi: Pi) {
  pi.command("phx-plan", async (args, ctx) => {
    return ctx.invoke_prompt("phx-plan", { args });
  });
  pi.command("phx-work", async (args, ctx) => {
    return ctx.invoke_prompt("phx-work", { args });
  });
  pi.command("phx-review", async (args, ctx) => {
    return ctx.invoke_prompt("phx-review", { args });
  });
}

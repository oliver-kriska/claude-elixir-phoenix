# Coupled Package Groups + Edge Cases

## Must-move-together groups

When ≥2 members of a group appear in the outdated set, force them into ONE
update step + commit — even if the user picked a narrower scope. If only
one member is outdated but a sibling pins it, `mix hex.outdated <pkg>`
surfaces the constraint.

| Group | Packages | Why |
|-------|----------|-----|
| Phoenix core | `phoenix`, `phoenix_html`, `phoenix_live_view`, `phoenix_live_dashboard`, `phoenix_ecto` | Shared protocols/JS; LV pins a phoenix range. Mismatch = compile/runtime errors. Triggers the JS-sync step |
| LV satellites | `phoenix_live_view` + LV-component libs present (`live_select`, `salad_ui`, ...) | They pin an LV version range |
| Ecto | `ecto`, `ecto_sql`, `postgrex` (+ `myxql`/`tds`) | `ecto_sql` pins `ecto`; the adapter pins `ecto_sql` |
| Ash | `ash`, `ash_postgres`, `ash_phoenix`, `ash_sql`, `ash_oban`, `ash_authentication` | Tight inter-version pinning; bump as a set |
| Telemetry | `telemetry`, `telemetry_metrics`, `telemetry_poller` | Shared core version |
| OpenTelemetry | `opentelemetry`, `opentelemetry_api`, `opentelemetry_exporter`, instrumentation libs | API/SDK lockstep |
| Oban | `oban`, `oban_pro`, `oban_web` | Pro/Web pin an `oban` range; Pro/Web are private (org auth + off-hex notes) |
| Absinthe | `absinthe`, `absinthe_plug`, `absinthe_phoenix` | Plug/Phoenix pin core |
| Asset installers | `tailwind`, `esbuild` | Installer bump may need a version bump in `config/config.exs` |

## Phoenix/JS coupling

A Phoenix-family bump with `assets/package.json` present requires:
`npm install --prefix assets` and staging `assets/package-lock.json` in
the SAME commit as `mix.lock` (Iron Law 5). The JS packages track the hex
versions (`file:../deps/phoenix` references).

## Edge cases

| Case | Detection | Handling |
|------|-----------|----------|
| Umbrella | `apps_path:` in mix.exs | `mix hex.outdated` from root iterates `apps/*`; updates apply at the root lock; snapshot changelogs from root `deps/` |
| Git deps | `git:` in tuple | Skipped by hex.outdated. Update via `mix deps.update <pkg>` (re-resolves ref); no hex changelog — link the git compare URL; flag "git dep — manual ref review" in inventory |
| Path deps | `path:` in tuple | Local, never outdated — exclude from inventory |
| Private orgs | `organization:`/`repo:` in tuple | Needs prior `mix hex.organization auth <org>`; on 401 tell the user, never handle keys |
| Blocked major | Status `Update not possible` | Edit mix.exs constraint; `override: true` only if a transitive consumer blocks (per-package hex.outdated table); one per PR |
| Greenfield (<10 .ex files) | file count | Skip area bucketing — bundle everything; coupled groups still apply |

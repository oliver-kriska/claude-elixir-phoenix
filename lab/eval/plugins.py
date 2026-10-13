"""Plugin discovery for the structural eval.

The scorers started out phx-only. These helpers let them score any plugin in
the marketplace: infer a file's plugin root from its path, map slash-command
namespaces (`phx`, `rewrite`, `ecto`, ...) to plugin directories, and name
which plugins the structural gate covers.
"""

import json
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PLUGINS_DIR = os.path.join(REPO_ROOT, "plugins")
DEFAULT_PLUGIN = "elixir-phoenix"

# Plugins whose skills and agents follow the phx structure and are scored by
# `make eval` / `make eval-all`. catchup, ecto and lv are not scored structurally.
STRUCTURAL_PLUGINS = ("elixir-phoenix", "rewrite")


# Domain keywords for `description_keywords` when a plugin is not the Elixir/Phoenix
# reference set the matcher defaults to. Substring matches, so keep them distinctive.
TRIGGER_KEYWORDS = {
    "rewrite": [
        "rewrite", "port", "migrat", "legacy", "elixir", "phoenix", "rails", "django", "laravel",
        "php", "node", "java", ".net", "architecture", "contract", "mechanism", "slice", "parity",
        "verify", "plan", "compatib", "ecto", "oban",
    ],
}


def plugin_dir(name: str) -> str:
    return os.path.join(PLUGINS_DIR, name)


def plugin_root_for(path: str) -> str:
    """Return the plugin directory containing `path`, or the default plugin."""
    current = os.path.abspath(path)
    while True:
        parent = os.path.dirname(current)
        if parent == current:
            return plugin_dir(DEFAULT_PLUGIN)
        if parent == PLUGINS_DIR and os.path.isfile(os.path.join(current, ".claude-plugin", "plugin.json")):
            return current
        current = parent


def plugin_name_for(path: str) -> str:
    return os.path.basename(plugin_root_for(path))


def namespace_map() -> dict[str, str]:
    """Map each manifest `name` (the slash-command namespace) to its plugin directory."""
    mapping = {}
    if not os.path.isdir(PLUGINS_DIR):
        return mapping
    for entry in sorted(os.listdir(PLUGINS_DIR)):
        manifest = os.path.join(PLUGINS_DIR, entry, ".claude-plugin", "plugin.json")
        try:
            with open(manifest, encoding="utf-8") as fh:
                mapping[json.load(fh)["name"]] = os.path.join(PLUGINS_DIR, entry)
        except (OSError, ValueError, KeyError):
            continue
    return mapping


def listing(root: str, kind: str) -> set[str]:
    """Skill directory names or agent basenames (without .md) in a plugin."""
    directory = os.path.join(root, kind)
    if not os.path.isdir(directory):
        return set()
    if kind == "agents":
        return {f[:-3] for f in os.listdir(directory) if f.endswith(".md")}
    return {d for d in os.listdir(directory) if os.path.isfile(os.path.join(directory, d, "SKILL.md"))}


def result_key(path: str, name: str) -> str:
    """Key used in `--all` output: bare for the default plugin, `plugin:name` otherwise."""
    plugin = plugin_name_for(path)
    return name if plugin == DEFAULT_PLUGIN else f"{plugin}:{name}"


def installed_plugins() -> list[str]:
    """Plugin directory names that carry a manifest."""
    if not os.path.isdir(PLUGINS_DIR):
        return []
    return [
        entry for entry in sorted(os.listdir(PLUGINS_DIR))
        if os.path.isfile(os.path.join(PLUGINS_DIR, entry, ".claude-plugin", "plugin.json"))
    ]


def unknown_plugins(names) -> list[str]:
    """Explicitly requested plugin names that match no installed plugin directory."""
    known = set(installed_plugins())
    return [name for name in names if name not in known]

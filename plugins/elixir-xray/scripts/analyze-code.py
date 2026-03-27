#!/usr/bin/env python3
"""Analyze Elixir code patterns, naming, documentation, i18n, and testing.

Deterministic static analysis — no LLM, no pip dependencies.
Outputs JSON to stdout (or to --output file).
"""

import argparse
import json
import os
import re
import subprocess
import sys


def find_files(root, ext, subdir=None):
    """Walk root (optionally under subdir) and yield paths ending with ext."""
    base = os.path.join(root, subdir) if subdir else root
    if not os.path.isdir(base):
        return
    for dirpath, _, filenames in os.walk(base):
        for f in filenames:
            if f.endswith(ext):
                yield os.path.join(dirpath, f)


def read_file_safe(path):
    """Read file, return content or empty string on error."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except (OSError, IOError):
        return ""


def relpath(path, root):
    """Return a relative path, falling back to the absolute path."""
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return path


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

def analyze_modules(repo, lib_dir):
    """Count modules, moduledoc coverage, largest files."""
    total = 0
    with_moduledoc = 0
    sizes = []

    for path in find_files(repo, ".ex", "lib"):
        total += 1
        content = read_file_safe(path)
        lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        sizes.append((path, lines))
        if re.search(r'@moduledoc\s', content):
            with_moduledoc += 1

    sizes.sort(key=lambda x: x[1], reverse=True)
    largest = [{"file": relpath(p, repo), "lines": n} for p, n in sizes[:10]]

    return {
        "total": total,
        "with_moduledoc": with_moduledoc,
        "moduledoc_coverage": round(with_moduledoc / total, 2) if total else 0,
        "largest_modules": largest,
    }


def analyze_functions(repo):
    """Categorize function names by prefix, detect inconsistencies."""
    prefixes = {
        "get_": 0, "fetch_": 0, "find_": 0, "list_": 0,
        "create_": 0, "update_": 0, "delete_": 0, "other": 0,
    }
    # Track prefix usage per context (parent directory name)
    context_prefixes = {}  # context_name -> set of prefixes used
    def_re = re.compile(r'^\s*def\s+([a-z_][a-z0-9_]*)')

    for path in find_files(repo, ".ex", "lib"):
        content = read_file_safe(path)
        # Derive context from the directory name relative to lib/APP/
        parts = relpath(path, repo).split(os.sep)
        # e.g. lib/my_app/accounts/user.ex -> context = accounts
        context = None
        if len(parts) >= 3 and parts[0] == "lib":
            context = parts[2] if len(parts) >= 4 else None
            # If file is directly under lib/app_name/, use filename as context
            if context is None:
                context = os.path.splitext(parts[-1])[0]

        for line in content.splitlines():
            m = def_re.match(line)
            if not m:
                continue
            fname = m.group(1)
            matched = False
            for prefix in list(prefixes.keys()):
                if prefix == "other":
                    continue
                if fname.startswith(prefix):
                    prefixes[prefix] += 1
                    matched = True
                    if context:
                        context_prefixes.setdefault(context, set()).add(prefix)
                    break
            if not matched:
                prefixes["other"] += 1

    # Detect inconsistencies: contexts using both get_ and find_, or fetch_ and find_
    inconsistencies = []
    for ctx, used in context_prefixes.items():
        # Check for retrieval inconsistency
        retrieval = used & {"get_", "fetch_", "find_"}
        if len(retrieval) >= 2:
            suggestion = "standardize to get_"
            inconsistencies.append({
                "context": ctx,
                "uses": sorted(retrieval),
                "suggestion": suggestion,
            })

    return {
        "naming_patterns": prefixes,
        "inconsistencies": inconsistencies,
    }


def analyze_i18n(repo):
    """Gettext usage, hardcoded strings in .heex, .po empty translations."""
    # Count modules importing Gettext
    gettext_modules = 0
    gettext_re = re.compile(r'(import\s+\S*Gettext|use\s+\S*Gettext|use\s+Gettext)')
    for path in find_files(repo, ".ex", "lib"):
        content = read_file_safe(path)
        if gettext_re.search(content):
            gettext_modules += 1

    # Hardcoded strings in .heex files
    # Match quoted strings that are NOT inside gettext/dgettext/ngettext/pgettext calls
    hardcoded_strings = []
    # Pattern: a quoted string that appears to be UI text (not an attribute value like class="...")
    # We look for strings that are text content (after > or at start), not inside gettext calls
    heex_str_re = re.compile(r'"([^"]{3,})"')
    gettext_call_re = re.compile(r'(gettext|dgettext|ngettext|pgettext|Gettext)\s*\(')
    # Skip common non-UI attributes
    attr_re = re.compile(r'(class|id|phx-|type|method|action|href|src|alt|name|value|placeholder|for|data-|role|aria-|style|encoding|csrf)=\s*"')

    for path in find_files(repo, ".heex", "lib"):
        content = read_file_safe(path)
        for i, line in enumerate(content.splitlines(), 1):
            # Skip lines that are gettext calls
            if gettext_call_re.search(line):
                continue
            # Skip attribute assignments
            if attr_re.search(line):
                # Could still have hardcoded text, but skip for now to reduce false positives
                continue
            # Skip comments
            stripped = line.strip()
            if stripped.startswith("<%#") or stripped.startswith("<!--"):
                continue
            for m in heex_str_re.finditer(line):
                text = m.group(1)
                # Filter out non-UI strings (paths, CSS, etc.)
                if (
                    "/" in text
                    or text.startswith(".")
                    or text.startswith("#")
                    or re.match(r'^[a-z_-]+$', text)  # likely CSS/attr
                    or re.match(r'^%', text)  # format strings
                    or len(text.split()) == 0
                ):
                    continue
                hardcoded_strings.append({
                    "file": relpath(path, repo),
                    "line": i,
                    "text": text[:80],
                })

    # .po files — count empty msgstr per locale
    po_stats = {}
    po_total = 0
    pot_total = 0
    po_msgstr_empty_re = re.compile(r'^msgstr\s+""\s*$', re.MULTILINE)
    po_msgid_re = re.compile(r'^msgid\s+"(.+)"', re.MULTILINE)

    for path in find_files(repo, ".po", "priv"):
        po_total += 1
        content = read_file_safe(path)
        # Extract locale from path: priv/gettext/LOCALE/LC_MESSAGES/...
        parts = path.split(os.sep)
        locale = "unknown"
        for j, part in enumerate(parts):
            if part == "gettext" and j + 1 < len(parts):
                locale = parts[j + 1]
                break

        # Count empty msgstr (excluding header)
        # Split into entries by double newline
        entries = re.split(r'\n\n+', content)
        empty_count = 0
        for entry in entries:
            if 'msgid ""' in entry and 'msgstr ""' in entry and "Project-Id-Version" in entry:
                continue  # Skip header
            if po_msgid_re.search(entry):
                # Check if msgstr is empty
                msgstr_match = re.search(r'^msgstr\s+"(.*)"', entry, re.MULTILINE)
                if msgstr_match and msgstr_match.group(1) == "":
                    empty_count += 1
        if empty_count > 0:
            po_stats[locale] = po_stats.get(locale, 0) + empty_count

    for path in find_files(repo, ".pot", "priv"):
        pot_total += 1

    return {
        "gettext_modules": gettext_modules,
        "hardcoded_strings_in_heex": len(hardcoded_strings),
        "hardcoded_examples": hardcoded_strings[:20],
        "po_files": {
            "total": po_total,
            "empty_translations": po_stats,
        },
        "pot_files": pot_total,
    }


def analyze_testing(repo):
    """Source vs test file counts, missing test coverage."""
    source_files = []
    for path in find_files(repo, ".ex", "lib"):
        source_files.append(relpath(path, repo))

    test_files = []
    for path in find_files(repo, ".exs", "test"):
        if path.endswith("_test.exs"):
            test_files.append(relpath(path, repo))

    # Build a map of test files for lookup
    # test/my_app/accounts/user_test.exs -> lib/my_app/accounts/user.ex
    test_basenames = set()
    for tf in test_files:
        # Remove test/ prefix and _test.exs suffix, add lib/ prefix and .ex suffix
        base = tf
        if base.startswith("test" + os.sep):
            base = base[len("test" + os.sep):]
        base = base.replace("_test.exs", ".ex")
        test_basenames.add(os.path.join("lib", base))

    missing = []
    for sf in source_files:
        # Skip files that are unlikely to need tests
        basename = os.path.basename(sf)
        if basename in ("application.ex", "repo.ex", "telemetry.ex", "mailer.ex", "gettext.ex"):
            continue
        if "_web" in sf and basename in ("endpoint.ex", "router.ex"):
            continue
        if sf not in test_basenames:
            missing.append(sf)

    total_source = len(source_files)
    total_test = len(test_files)

    return {
        "source_files": total_source,
        "test_files": total_test,
        "coverage_ratio": round(total_test / total_source, 2) if total_source else 0,
        "missing_tests": missing[:50],
    }


def analyze_validations(repo):
    """Count changeset definitions and validation calls."""
    validations = {
        "validate_required": 0,
        "validate_format": 0,
        "validate_length": 0,
        "validate_inclusion": 0,
        "validate_exclusion": 0,
        "validate_number": 0,
        "validate_acceptance": 0,
        "validate_confirmation": 0,
        "validate_change": 0,
        "validate_subset": 0,
        "unique_constraint": 0,
        "foreign_key_constraint": 0,
        "check_constraint": 0,
        "no_assoc_constraint": 0,
    }
    changeset_count = 0
    changeset_re = re.compile(r'def\s+changeset\b')

    for path in find_files(repo, ".ex", "lib"):
        content = read_file_safe(path)
        changeset_count += len(changeset_re.findall(content))
        for vname in validations:
            validations[vname] += len(re.findall(r'\b' + vname + r'\b', content))

    # Filter out zero-count validations for cleaner output
    common = {k: v for k, v in validations.items() if v > 0}

    return {
        "changeset_count": changeset_count,
        "common_validations": common,
    }


def analyze_documentation(repo):
    """README, CLAUDE.md, markdown count, @doc coverage sample."""
    has_readme = os.path.isfile(os.path.join(repo, "README.md"))
    has_claude_md = os.path.isfile(os.path.join(repo, "CLAUDE.md"))

    md_count = 0
    for _ in find_files(repo, ".md"):
        md_count += 1

    # Sample top 20 largest modules for @doc coverage
    modules_with_size = []
    for path in find_files(repo, ".ex", "lib"):
        content = read_file_safe(path)
        lines = content.count("\n")
        modules_with_size.append((path, content, lines))

    modules_with_size.sort(key=lambda x: x[2], reverse=True)
    sample = modules_with_size[:20]

    doc_re = re.compile(r'@doc\s')
    public_fn_re = re.compile(r'^\s*def\s+[a-z]', re.MULTILINE)
    total_public = 0
    total_documented = 0

    for path, content, _ in sample:
        pub_count = len(public_fn_re.findall(content))
        doc_count = len(doc_re.findall(content))
        total_public += pub_count
        total_documented += min(doc_count, pub_count)

    return {
        "has_readme": has_readme,
        "has_claude_md": has_claude_md,
        "markdown_files": md_count,
        "doc_coverage_sample": round(total_documented / total_public, 2) if total_public else 0,
    }


def analyze_contexts(repo):
    """List directories under lib/APP_NAME/ (Phoenix contexts)."""
    lib_dir = os.path.join(repo, "lib")
    if not os.path.isdir(lib_dir):
        return []

    # Find the app name directory (non-web, first-level under lib/)
    app_dirs = []
    for entry in sorted(os.listdir(lib_dir)):
        full = os.path.join(lib_dir, entry)
        if os.path.isdir(full) and not entry.endswith("_web") and not entry.startswith("."):
            app_dirs.append((entry, full))

    contexts = []
    for app_name, app_dir in app_dirs:
        for entry in sorted(os.listdir(app_dir)):
            ctx_dir = os.path.join(app_dir, entry)
            if not os.path.isdir(ctx_dir):
                continue
            mod_count = 0
            for _ in find_files(ctx_dir, ".ex"):
                mod_count += 1
            if mod_count > 0:
                contexts.append({
                    "name": entry,
                    "modules": mod_count,
                    "path": relpath(ctx_dir, repo) + "/",
                })

    return contexts


def analyze_dependencies(repo):
    """Parse mix.exs to extract dependency names."""
    mix_path = os.path.join(repo, "mix.exs")
    if not os.path.isfile(mix_path):
        return []

    content = read_file_safe(mix_path)
    # Match {:dep_name, ...} patterns inside a deps function
    dep_re = re.compile(r'\{:(\w+),')
    deps = []
    in_deps = False
    brace_depth = 0
    for line in content.splitlines():
        if re.search(r'def[p]?\s+deps\b', line):
            in_deps = True
        if in_deps:
            brace_depth += line.count("[") - line.count("]")
            m = dep_re.search(line)
            if m:
                deps.append(m.group(1))
            if brace_depth <= 0 and in_deps and deps:
                break

    return sorted(set(deps))


def analyze_dependency_freshness(repo, dep_names):
    """Check dependency freshness by comparing mix.lock versions against latest on Hex.

    Args:
        repo: Path to the Elixir project root.
        dep_names: List of dependency names from analyze_dependencies().

    Returns a dict with total_deps, outdated count, and outdated_list with version details.
    """
    if not dep_names:
        return {"total_deps": 0, "outdated": 0, "outdated_list": []}

    # Parse current versions from mix.lock
    lock_path = os.path.join(repo, "mix.lock")
    current_versions = {}
    if os.path.isfile(lock_path):
        lock_content = read_file_safe(lock_path)
        # mix.lock format: "dep_name": {:hex, :dep_name, "version", ...}
        lock_re = re.compile(r'"(\w+)":\s*\{:hex,\s*:\w+,\s*"([^"]+)"')
        for m in lock_re.finditer(lock_content):
            current_versions[m.group(1)] = m.group(2)

    if not current_versions:
        return {"total_deps": len(dep_names), "outdated": 0, "outdated_list": [],
                "note": "Could not parse mix.lock"}

    # Check if mix is available
    try:
        subprocess.run(["mix", "--version"], capture_output=True, timeout=5)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"total_deps": len(dep_names), "outdated": 0, "outdated_list": [],
                "note": "mix not available"}

    # Check freshness for up to 20 deps
    deps_to_check = [d for d in dep_names if d in current_versions][:20]
    outdated_list = []

    for dep in deps_to_check:
        current = current_versions.get(dep)
        if not current:
            continue
        try:
            result = subprocess.run(
                ["mix", "hex.info", dep],
                capture_output=True, text=True, timeout=5, cwd=repo,
            )
            if result.returncode != 0:
                continue
            # Parse latest version from hex.info output
            # Output format includes a line like: "Config: {:dep_name, \"~> X.Y\"}"
            # or a versions list. Look for the first version line or "Latest release" line.
            output = result.stdout
            # Try to find a version pattern — hex.info prints versions list
            # Typical output: "phoenix\n  Releases: 1.8.3, 1.8.2, 1.8.1, ..."
            # or structured output with "Latest release:" line
            latest = None
            for line in output.splitlines():
                line_stripped = line.strip()
                # Match "Releases: X.Y.Z, ..." pattern (first version is latest)
                rel_match = re.match(r'Releases:\s*([\d]+\.[\d]+\.[\d]+\S*)', line_stripped)
                if rel_match:
                    latest = rel_match.group(1)
                    break
                # Match "Latest release: X.Y.Z" pattern
                lr_match = re.match(r'Latest release:\s*([\d]+\.[\d]+\.[\d]+\S*)', line_stripped)
                if lr_match:
                    latest = lr_match.group(1)
                    break
            if not latest or latest == current:
                continue

            # Estimate months behind using version numbers (rough heuristic)
            months_behind = _estimate_months_behind(current, latest)

            outdated_list.append({
                "name": dep,
                "current": current,
                "latest": latest,
                "months_behind": months_behind,
            })
        except (subprocess.TimeoutExpired, OSError):
            continue

    return {
        "total_deps": len(dep_names),
        "checked": len(deps_to_check),
        "outdated": len(outdated_list),
        "outdated_list": outdated_list,
    }


def _estimate_months_behind(current, latest):
    """Rough estimate of months behind based on version difference.

    Uses a heuristic: major version diff = 12 months per major,
    minor diff = 3 months per minor, patch = 1 month per 3 patches.
    Returns None if versions can't be parsed.
    """
    try:
        cur_parts = [int(x) for x in current.split(".")[:3]]
        lat_parts = [int(x) for x in latest.split(".")[:3]]
        while len(cur_parts) < 3:
            cur_parts.append(0)
        while len(lat_parts) < 3:
            lat_parts.append(0)

        major_diff = lat_parts[0] - cur_parts[0]
        minor_diff = lat_parts[1] - cur_parts[1]
        patch_diff = lat_parts[2] - cur_parts[2]

        months = major_diff * 12 + minor_diff * 3 + max(patch_diff // 3, 0)
        return max(months, 0) if months >= 0 else None
    except (ValueError, IndexError):
        return None


def analyze_existing_credo_checks(repo):
    """Find and catalog custom Credo checks in the project."""
    checks = []

    # Scan all .ex files under lib/ for files that use Credo.Check
    for path in find_files(repo, ".ex", "lib"):
        content = read_file_safe(path)
        if not re.search(r'use\s+Credo\.Check\b', content):
            continue

        # Extract module name
        mod_match = re.search(r'defmodule\s+([\w.]+)', content)
        module = mod_match.group(1) if mod_match else "unknown"

        # Extract category from use Credo.Check, ... category: :atom
        cat_match = re.search(r'use\s+Credo\.Check\b.*?category:\s*:(\w+)', content)
        category = cat_match.group(1) if cat_match else "unknown"

        # Extract base_priority from use Credo.Check, ... base_priority: :atom
        pri_match = re.search(r'use\s+Credo\.Check\b.*?base_priority:\s*:(\w+)', content)
        priority = pri_match.group(1) if pri_match else "normal"

        # Extract first line of @moduledoc or @explanation
        description = ""
        # Try @moduledoc first
        moddoc_match = re.search(
            r'@moduledoc\s+"""(.*?)"""', content, re.DOTALL
        )
        if moddoc_match:
            first_line = moddoc_match.group(1).strip().split("\n")[0].strip()
            if first_line:
                description = first_line[:120]

        # Fall back to @explanation if no @moduledoc description
        if not description:
            expl_match = re.search(
                r'@explanation\s+\[.*?check:\s*"""(.*?)"""', content, re.DOTALL
            )
            if expl_match:
                first_line = expl_match.group(1).strip().split("\n")[0].strip()
                if first_line:
                    description = first_line[:120]

        # Second fallback: @explanation as a simple string
        if not description:
            expl_str_match = re.search(
                r'@explanation\s+"([^"]+)"', content
            )
            if expl_str_match:
                description = expl_str_match.group(1)[:120]

        checks.append({
            "file": relpath(path, repo),
            "module": module,
            "category": category,
            "priority": priority,
            "description": description,
        })

    # Sort by category then module for stable output
    checks.sort(key=lambda c: (c["category"], c["module"]))

    return {
        "count": len(checks),
        "checks": checks,
    }


def analyze_project_description(repo):
    """Read the first 500 characters of README.md for domain context."""
    readme_path = os.path.join(repo, "README.md")
    if not os.path.isfile(readme_path):
        return None

    try:
        with open(readme_path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read(500)
    except (OSError, IOError):
        return None

    # Strip leading badges/images for cleaner output
    # Remove lines that are only markdown images or badges
    lines = content.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Skip pure image/badge lines
        if re.match(r'^!\[', stripped) or re.match(r'^\[!\[', stripped):
            continue
        # Skip empty lines at the start
        if not cleaned and not stripped:
            continue
        cleaned.append(line)

    return "\n".join(cleaned).strip()[:500]


def detect_ash(repo):
    """Check for Ash Framework usage."""
    for path in find_files(repo, ".ex", "lib"):
        content = read_file_safe(path)
        if re.search(r'use\s+Ash\.(Resource|Domain)\b', content):
            return True
    return False


# ---------------------------------------------------------------------------
# Deep-scan analysis helpers
# ---------------------------------------------------------------------------

def analyze_auth_audit(repo):
    """Scan LiveView handle_event functions for authorization checks."""
    auth_patterns = re.compile(
        r'\b(authorize|verify|check_permission|Bodyguard|Canada|LetMe|Policy|allowed\?|can\?)\b'
    )
    handle_event_re = re.compile(r'^\s*def\s+handle_event\s*\(\s*"([^"]+)"')

    total_events = 0
    authorized_events = 0
    unguarded_events = []

    for path in find_files(repo, ".ex", "lib"):
        if not path.endswith("_live.ex"):
            continue
        content = read_file_safe(path)
        lines = content.splitlines()
        for i, line in enumerate(lines):
            m = handle_event_re.match(line)
            if not m:
                continue
            event_name = m.group(1)
            total_events += 1
            # Check the next 20 lines for authorization patterns
            body_window = "\n".join(lines[i:i + 20])
            if auth_patterns.search(body_window):
                authorized_events += 1
            else:
                unguarded_events.append({
                    "file": relpath(path, repo),
                    "event": event_name,
                    "line": i + 1,
                })

    return {
        "total_events": total_events,
        "authorized": authorized_events,
        "unguarded": total_events - authorized_events,
        "unguarded_events": unguarded_events,
    }


def analyze_feature_flags(repo):
    """Detect feature flag library usage and flag references."""
    lib_patterns = {
        "FunWithFlags": re.compile(r'\bFunWithFlags\b'),
        "LaunchDarkly": re.compile(r'\bLaunchDarkly\b'),
        "ConfigCat": re.compile(r'\bConfigCat\b'),
        "Flipper": re.compile(r'\bFlipper\b'),
    }
    generic_patterns = re.compile(
        r'\b(feature_flag|feature_enabled|Feature\.enabled\?|FF\.active\?)\b'
    )
    flag_name_re = re.compile(r'(?:feature_flag|enabled\?|active\?)\s*\(\s*:(\w+)')

    detected_library = "none"
    usage_count = 0
    files_with_flags = set()
    flag_names = set()

    # Check mix.exs deps
    mix_path = os.path.join(repo, "mix.exs")
    if os.path.isfile(mix_path):
        mix_content = read_file_safe(mix_path)
        for lib_name in lib_patterns:
            if lib_name.lower().replace(" ", "_") in mix_content.lower():
                detected_library = lib_name

    for path in find_files(repo, ".ex", "lib"):
        content = read_file_safe(path)
        rel = relpath(path, repo)
        for lib_name, pat in lib_patterns.items():
            matches = pat.findall(content)
            if matches:
                detected_library = lib_name
                usage_count += len(matches)
                files_with_flags.add(rel)
        gen_matches = generic_patterns.findall(content)
        if gen_matches:
            if detected_library == "none":
                detected_library = "custom"
            usage_count += len(gen_matches)
            files_with_flags.add(rel)
        for fm in flag_name_re.finditer(content):
            flag_names.add(fm.group(1))

    return {
        "library": detected_library,
        "usage_count": usage_count,
        "files": sorted(files_with_flags),
        "flag_names": sorted(flag_names),
    }


def analyze_soft_delete(repo):
    """Find schemas with :deleted_at and queries that may miss the filter."""
    deleted_at_re = re.compile(r'field\s+:deleted_at\b')
    schema_name_re = re.compile(r'schema\s+"(\w+)"')

    schemas_with_deleted_at = []
    schema_table_names = set()

    # Pass 1: find schemas with deleted_at
    for path in find_files(repo, ".ex", "lib"):
        content = read_file_safe(path)
        if deleted_at_re.search(content):
            rel = relpath(path, repo)
            schemas_with_deleted_at.append(rel)
            for sm in schema_name_re.finditer(content):
                schema_table_names.add(sm.group(1))

    # Pass 2: find queries referencing those tables without deleted_at filter
    unfiltered_examples = []
    if schema_table_names:
        table_re = re.compile(
            r'\bfrom\b.*\b(' + '|'.join(re.escape(t) for t in schema_table_names) + r')\b'
        )
        for path in find_files(repo, ".ex", "lib"):
            content = read_file_safe(path)
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if table_re.search(line):
                    # Check surrounding context (this line + next 10) for deleted_at
                    window = "\n".join(lines[i:i + 10])
                    if "deleted_at" not in window:
                        unfiltered_examples.append({
                            "file": relpath(path, repo),
                            "line": i + 1,
                        })

    return {
        "schemas_with_deleted_at": len(schemas_with_deleted_at),
        "schema_files": schemas_with_deleted_at,
        "queries_without_filter": len(unfiltered_examples),
        "unfiltered_examples": unfiltered_examples[:30],
    }


def analyze_money_fields(repo):
    """Audit schema fields that likely represent money for :float violations."""
    money_names = {"amount", "price", "cost", "total", "fee", "balance", "rate"}
    field_re = re.compile(
        r'field\s+:(\w+)\s*,\s*:(\w+)'
    )

    total_money = 0
    float_violations = []
    decimal_correct = 0

    for path in find_files(repo, ".ex", "lib"):
        content = read_file_safe(path)
        for m in field_re.finditer(content):
            field_name = m.group(1)
            field_type = m.group(2)
            # Check if the field name contains a money-related keyword
            if not any(kw in field_name for kw in money_names):
                continue
            total_money += 1
            if field_type == "float":
                float_violations.append({
                    "file": relpath(path, repo),
                    "field": field_name,
                    "type": "float",
                })
            elif field_type in ("decimal", "integer"):
                decimal_correct += 1

    return {
        "total_money_fields": total_money,
        "float_violations": len(float_violations),
        "violations": float_violations,
        "decimal_correct": decimal_correct,
    }


def analyze_error_patterns(repo):
    """Count error-handling patterns per context directory."""
    lib_dir = os.path.join(repo, "lib")
    if not os.path.isdir(lib_dir):
        return {"by_context": [], "summary": {"total_raises": 0, "total_rescues": 0, "total_logger_errors": 0}}

    # Find app directories (non-web, first-level under lib/)
    app_dirs = []
    for entry in sorted(os.listdir(lib_dir)):
        full = os.path.join(lib_dir, entry)
        if os.path.isdir(full) and not entry.startswith("."):
            app_dirs.append((entry, full))

    ok_re = re.compile(r'\{:ok\b')
    error_re = re.compile(r'\{:error\b')
    raise_re = re.compile(r'\braise\s')
    rescue_re = re.compile(r'\brescue\b')
    logger_error_re = re.compile(r'\bLogger\.error\b')
    logger_warn_re = re.compile(r'\bLogger\.warning\b')

    by_context = []
    total_raises = 0
    total_rescues = 0
    total_logger_errors = 0

    for app_name, app_dir in app_dirs:
        for entry in sorted(os.listdir(app_dir)):
            ctx_dir = os.path.join(app_dir, entry)
            if not os.path.isdir(ctx_dir):
                continue

            ctx_ok = 0
            ctx_error = 0
            ctx_raises = 0
            ctx_rescues = 0
            ctx_logger_errors = 0
            ctx_logger_warnings = 0

            for path in find_files(ctx_dir, ".ex"):
                content = read_file_safe(path)
                ctx_ok += len(ok_re.findall(content))
                ctx_error += len(error_re.findall(content))
                ctx_raises += len(raise_re.findall(content))
                ctx_rescues += len(rescue_re.findall(content))
                ctx_logger_errors += len(logger_error_re.findall(content))
                ctx_logger_warnings += len(logger_warn_re.findall(content))

            if any([ctx_ok, ctx_error, ctx_raises, ctx_rescues, ctx_logger_errors, ctx_logger_warnings]):
                by_context.append({
                    "context": os.path.join(app_name, entry),
                    "ok_tuples": ctx_ok,
                    "error_tuples": ctx_error,
                    "raises": ctx_raises,
                    "rescues": ctx_rescues,
                    "logger_errors": ctx_logger_errors,
                    "logger_warnings": ctx_logger_warnings,
                })
                total_raises += ctx_raises
                total_rescues += ctx_rescues
                total_logger_errors += ctx_logger_errors

    return {
        "by_context": by_context,
        "summary": {
            "total_raises": total_raises,
            "total_rescues": total_rescues,
            "total_logger_errors": total_logger_errors,
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Analyze Elixir code patterns, naming, documentation, i18n, and testing."
    )
    parser.add_argument("repo_path", help="Path to the Elixir project root")
    parser.add_argument("--full", action="store_true", help="Deep domain analysis (includes all contexts)")
    parser.add_argument("--since", help="Only analyze files changed since this commit (git ref)")
    parser.add_argument("--output", help="Write JSON to this file instead of stdout")
    args = parser.parse_args()

    repo = os.path.abspath(args.repo_path)
    if not os.path.isdir(repo):
        print(json.dumps({"error": f"Not a directory: {repo}"}), file=sys.stderr)
        sys.exit(1)

    lib_dir = os.path.join(repo, "lib")
    mix_file = os.path.join(repo, "mix.exs")
    if not os.path.isdir(lib_dir) or not os.path.isfile(mix_file):
        print(json.dumps({"error": "Not an Elixir project (missing lib/ or mix.exs)"}), file=sys.stderr)
        sys.exit(1)

    # Incremental mode: if --since provided, record changed files for context
    changed_files = None
    if args.since:
        try:
            git_out = subprocess.run(
                ["git", "diff", "--name-only", f"{args.since}...HEAD"],
                capture_output=True, text=True, cwd=repo, timeout=30
            )
            if git_out.returncode == 0:
                changed_files = set(git_out.stdout.strip().split("\n")) if git_out.stdout.strip() else set()
                print(f"Incremental mode: {len(changed_files)} files changed since {args.since}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: --since failed ({e}), running full analysis", file=sys.stderr)

    deps = analyze_dependencies(repo)

    result = {
        "modules": analyze_modules(repo, lib_dir),
        "functions": analyze_functions(repo),
        "i18n": analyze_i18n(repo),
        "testing": analyze_testing(repo),
        "validations": analyze_validations(repo),
        "documentation": analyze_documentation(repo),
        "contexts": analyze_contexts(repo),
        "dependencies": deps,
        "dependency_freshness": analyze_dependency_freshness(repo, deps),
        "existing_credo_checks": analyze_existing_credo_checks(repo),
        "project_description": analyze_project_description(repo),
        "ash_detected": detect_ash(repo),
        "auth_audit": analyze_auth_audit(repo),
        "feature_flags": analyze_feature_flags(repo),
        "soft_delete": analyze_soft_delete(repo),
        "money_fields": analyze_money_fields(repo),
        "error_patterns": analyze_error_patterns(repo),
    }

    # Add incremental mode metadata if --since was used
    if changed_files is not None:
        result["incremental"] = {
            "since": args.since,
            "changed_files": sorted(changed_files)[:50],
            "total_changed": len(changed_files),
        }

    # Cap large arrays to keep JSON under ~10K tokens for agent consumption
    if "modules" in result:
        mods = result["modules"]
        if "largest_modules" in mods:
            mods["largest_modules"] = mods["largest_modules"][:15]
    if "i18n" in result:
        i18n = result["i18n"]
        if "hardcoded_examples" in i18n:
            i18n["hardcoded_examples"] = i18n["hardcoded_examples"][:20]
    if "testing" in result:
        testing = result["testing"]
        if "missing_tests" in testing:
            testing["missing_tests"] = testing["missing_tests"][:30]
    if "functions" in result:
        funcs = result["functions"]
        if "inconsistencies" in funcs:
            funcs["inconsistencies"] = funcs["inconsistencies"][:20]
    if "auth_audit" in result:
        auth = result["auth_audit"]
        if "unguarded_events" in auth:
            auth["unguarded_events"] = auth["unguarded_events"][:30]
    if "soft_delete" in result:
        sd = result["soft_delete"]
        if "unfiltered_examples" in sd:
            sd["unfiltered_examples"] = sd["unfiltered_examples"][:20]
    if "error_patterns" in result:
        ep = result["error_patterns"]
        if "by_context" in ep:
            ep["by_context"] = ep["by_context"][:20]

    output = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        out_dir = os.path.dirname(args.output)
        if out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(output + "\n")
        print(f"Output written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()

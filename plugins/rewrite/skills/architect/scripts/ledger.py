#!/usr/bin/env python3
"""Deterministic checks and counts for the rewrite ledger (.claude/rewrite/ledger.md).

check  — every M-/R-/C- ID defined in analysis/*.md is the ID (or an alias) of
         exactly one ledger row, rows match their table's width, verdict and
         state values are valid, ADR references resolve, and every AR-NN
         departure has a complete record that scopes the row.
stats  — counts by verdict, implementation, evidence and departure, with the
         verified numerator kept separate from retired and accepted-risk rows.

Stdlib only. Reads files, never writes them.

Usage:
    python3 ledger.py check [--rewrite-dir .claude/rewrite]
    python3 ledger.py stats [--rewrite-dir .claude/rewrite] [--ids M-01,C-04 | --slice interview.md] [--json]

Exit status: 0 clean, 1 ledger errors (stats too: malformed rows, no ledger table, missing
columns), 2 unusable input (missing ledger or slice).
"""

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter

ID_RE = re.compile(r"\b([MRC]-\d{2,}[a-z]?)\b")
ROW_ID_RE = re.compile(r"^\|\s*[*`_]*([MRC]-\d{2,}[a-z]?)\b")
SEPARATOR_RE = re.compile(r"^\|[\s:|-]+\|?$")
ADR_RE = re.compile(r"\bADR-(\d{3})\b")
AR_RE = re.compile(r"AR-\d{2,}")
AR_FIELDS = ("owner", "scope", "rationale", "review", "approved")
PLACEHOLDER_RE = re.compile(r"^(|—|-|\?|tbd|todo|pending|none|n/a|<[^>]*>)$", re.I)
NO_DEPARTURE = ("", "none", "—", "-")
VERDICTS = {"MAP", "REPLACE", "KEEP", "SHIM", "DELETE", "UNDECIDED"}
IMPL_STATES = {"pending", "implemented", "retired"}
EVIDENCE_STATES = {"not-run", "pass", "fail", "blocked", "stale"}


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def read_required(path):
    """Contents of `path`, or None when it cannot be read (unlike read(), which returns "")."""
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return None


def split_row(line):
    # Escaped pipes (`a \| b`) stay inside their cell.
    cells = re.split(r"(?<!\\)\|", line.strip().strip("|"))
    return [re.sub(r"[*`]", "", c.replace("\\|", "|")).strip() for c in cells]


def tables(text):
    """Yield (header, data_rows) for each markdown table in `text`."""
    block = []
    for line in text.splitlines() + [""]:
        if line.startswith("|"):
            block.append(line)
            continue
        if len(block) >= 2 and SEPARATOR_RE.match(block[1]):
            yield [h.lower() for h in split_row(block[0])], block[2:]
        block = []


def column(header, *names):
    for name in names:
        for i, h in enumerate(header):
            if h == name or h.startswith(name):
                return i
    return None


def is_ledger_header(header):
    return bool(header) and header[0] == "id" and column(header, "verdict") is not None


def rows_as_dicts(text):
    """Rows of every ledger table (an `ID` first column and a `Verdict` column), each read
    with its own table's header. Returns (table_columns, rows, malformed), where
    table_columns lists, per ledger table, which axis columns its header has.

    A row that mentions an ID but has none in its first cell, or whose width differs
    from the header, is malformed: it fails the check instead of vanishing from counts."""
    table_columns, out, malformed = [], [], []
    for header, lines in tables(text):
        if not is_ledger_header(header):
            continue
        idx = {
            "verdict": column(header, "verdict"),
            "impl": column(header, "impl", "implementation"),
            "evidence": column(header, "evidence state", "evidence"),
            "departure": column(header, "departure"),
        }
        table_columns.append({k: i is not None for k, i in idx.items()})
        for line in lines:
            cells = split_row(line)
            match = ROW_ID_RE.match(line) and ID_RE.search(cells[0])
            if not match:
                if ID_RE.search(line):
                    malformed.append(f"no ID in first cell: {line[:80]}")
                continue
            if len(cells) != len(header):
                malformed.append(f"{len(cells)} cells, header has {len(header)}: {line[:80]}")
                continue

            def cell(key):
                i = idx[key]
                return cells[i] if i is not None and i < len(cells) else ""
            out.append({
                "id": match.group(1),
                "aliases": ID_RE.findall(cells[0]),
                "verdict": cell("verdict"),
                "impl": cell("impl").lower(),
                "evidence": cell("evidence").lower(),
                "departure": cell("departure"),
                "has": {k: i is not None for k, i in idx.items()},
            })
    return table_columns, out, malformed


def defined_ids(rewrite_dir):
    ids = {}
    for path in sorted(glob.glob(os.path.join(rewrite_dir, "analysis", "*.md"))):
        for line in read(path).splitlines():
            if ROW_ID_RE.match(line):
                for alias in ID_RE.findall(split_row(line)[0]):
                    ids.setdefault(alias, os.path.basename(path))
    return ids


def structure_errors(table_columns, malformed):
    """Structural problems shared by check and stats: no ledger table, a table missing a
    required axis column, malformed rows. A complete table never masks an incomplete one."""
    if not table_columns:
        return ["ledger.md has no ledger table (header starting `| ID |` with a Verdict column)"]
    errors = []
    for n, has in enumerate(table_columns, 1):
        label = "ledger table" if len(table_columns) == 1 else f"ledger table {n}"
        errors += [f"{label} has no '{key}' column" for key in ("impl", "evidence") if not has[key]]
    return errors + [f"malformed ledger row ({line})" for line in malformed]


def risk_records(text):
    """{AR-NN: {field: value}} for each `## AR-NN` section of accepted-risks.md."""
    records, current = {}, None
    for line in text.splitlines():
        heading = re.match(r"^## (AR-\d{2,})\b", line)
        if heading:
            current = records.setdefault(heading.group(1), {})
            continue
        if line.startswith("#"):
            current = None
            continue
        field = re.match(r"^\s*[-*]\s*\**([A-Za-z ]+?)\**\s*:\**\s*(.*)$", line)
        if current is not None and field:
            name = field.group(1).strip().lower()
            if name in AR_FIELDS:
                current[name] = field.group(2).strip()
    return records


def risk_errors(row, ar, record):
    if record is None:
        return [f"{row['id']}: {ar} has no section in verify/accepted-risks.md"]
    errors = [f"{row['id']}: {ar} has no {name.capitalize()}"
              for name in AR_FIELDS if PLACEHOLDER_RE.match(record.get(name, ""))]
    scope = set(ID_RE.findall(record.get("scope", "")))
    if record.get("scope") and not scope & set(row["aliases"]):
        errors.append(f"{row['id']}: {ar} Scope does not list {row['id']}")
    return errors


def verdict_parts(value):
    return [p.strip().upper() for p in re.split(r"→|->|/", value) if p.strip()]


def check(rewrite_dir):
    warnings = []
    ledger_path = os.path.join(rewrite_dir, "ledger.md")
    text = read(ledger_path)
    if not text:
        return [f"missing {ledger_path}"], []
    table_columns, rows, malformed = rows_as_dicts(text)
    errors = structure_errors(table_columns, malformed)
    if not table_columns:
        return errors, []
    for n, has in enumerate(table_columns, 1):
        if not has["departure"]:
            label = "ledger table" if len(table_columns) == 1 else f"ledger table {n}"
            warnings.append(f"{label} has no 'departure' column; accepted risks cannot be recorded")
    risks = risk_records(read(os.path.join(rewrite_dir, "verify", "accepted-risks.md")))
    # Only row IDs and their aliases account for a mechanism; prose mentions do not.
    accounted = Counter(alias for r in rows for alias in set(r["aliases"]))
    missing = [(i, s) for i, s in defined_ids(rewrite_dir).items() if i not in accounted]
    errors += [f"{i} (defined in {s}) is not accounted for in the ledger" for i, s in missing]
    if missing:
        warnings.append("only a row's ID cell accounts for an ID, prose does not; a mechanism the "
                        "legacy lacks gets a DELETE row ('absent in legacy')")
    errors += [f"{i} appears in {n} ledger rows" for i, n in sorted(accounted.items()) if n > 1]
    for r in rows:
        parts = verdict_parts(r["verdict"])
        bad = [p for p in parts if p not in VERDICTS]
        if not parts or bad:
            errors.append(f"{r['id']}: verdict '{r['verdict']}' not in {sorted(VERDICTS)}")
        if r["has"]["impl"] and r["impl"] not in IMPL_STATES:
            errors.append(f"{r['id']}: implementation '{r['impl']}' not in {sorted(IMPL_STATES)}")
        if r["has"]["evidence"] and r["evidence"] not in EVIDENCE_STATES:
            errors.append(f"{r['id']}: evidence '{r['evidence']}' not in {sorted(EVIDENCE_STATES)}")
        if r["has"]["departure"] and r["departure"] == "":
            errors.append(f"{r['id']}: empty departure cell (write 'none' or AR-NN)")
        elif r["departure"] not in NO_DEPARTURE:
            if not AR_RE.fullmatch(r["departure"]):
                errors.append(f"{r['id']}: departure '{r['departure']}' is neither 'none' nor AR-NN")
            else:
                errors += risk_errors(r, r["departure"], risks.get(r["departure"]))
        if "UNDECIDED" in verdict_parts(r["verdict"]) and r["impl"] == "implemented":
            warnings.append(f"{r['id']}: implemented while its verdict is UNDECIDED")
    arch = os.path.join(rewrite_dir, "architecture")
    refs = set()
    for path in [ledger_path] + glob.glob(os.path.join(arch, "*.md")):
        refs.update(ADR_RE.findall(read(path)))
    for num in sorted(refs):
        if num == "000":
            if not glob.glob(os.path.join(arch, "ADR-000*.md")):
                errors.append("ADR-000 referenced but architecture/ADR-000-*.md is missing")
        elif not glob.glob(os.path.join(arch, "adr", f"ADR-{num}*.md")):
            errors.append(f"ADR-{num} referenced but architecture/adr/ADR-{num}-*.md is missing")
    return errors, warnings


def stats(rewrite_dir, ids=None):
    _, rows, _ = rows_as_dicts(read(os.path.join(rewrite_dir, "ledger.md")))
    if ids is not None:
        rows = [r for r in rows if set(r["aliases"]) & ids]
    verdicts, impl, evidence = Counter(), Counter(), Counter()
    departures = 0
    verified = 0
    for r in rows:
        for part in verdict_parts(r["verdict"])[-1:]:
            verdicts[part] += 1
        impl[r["impl"] or "?"] += 1
        evidence[r["evidence"] or "?"] += 1
        has_departure = r["departure"] not in NO_DEPARTURE
        departures += has_departure
        if r["impl"] == "implemented" and r["evidence"] == "pass" and not has_departure:
            verified += 1
    retired = impl.get("retired", 0)
    return {
        "rows": len(rows),
        "verified": verified,
        "denominator": len(rows) - retired,
        "retired": retired,
        "accepted_risk": departures,
        "undecided": verdicts.get("UNDECIDED", 0),
        "verdicts": dict(sorted(verdicts.items())),
        "implementation": dict(sorted(impl.items())),
        "evidence": dict(sorted(evidence.items())),
    }


def format_stats(s):
    lines = [
        f"verified {s['verified']} of {s['denominator']} ledger rows (retired {s['retired']}, "
        f"accepted risk {s['accepted_risk']}, UNDECIDED {s['undecided']})",
        "verdicts: " + ", ".join(f"{k} {v}" for k, v in s["verdicts"].items()),
        "implementation: " + ", ".join(f"{k} {v}" for k, v in s["implementation"].items()),
        "evidence: " + ", ".join(f"{k} {v}" for k, v in s["evidence"].items()),
    ]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["check", "stats"])
    ap.add_argument("--rewrite-dir", default=".claude/rewrite")
    ap.add_argument("--ids", help="comma-separated ledger IDs to count")
    ap.add_argument("--slice", help="count only IDs mentioned in this file (a slice interview.md)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.command == "check":
        errors, warnings = check(args.rewrite_dir)
        for w in warnings:
            print(f"warning: {w}")
        for e in errors:
            print(f"error: {e}")
        print("ledger OK" if not errors else f"{len(errors)} error(s)")
        return 1 if errors else 0
    if not read(os.path.join(args.rewrite_dir, "ledger.md")):
        print(f"error: missing {os.path.join(args.rewrite_dir, 'ledger.md')}")
        return 2
    ids = None
    if args.ids is not None:
        ids = {i.strip() for i in args.ids.split(",") if i.strip()}
    if args.slice:
        text = read_required(args.slice)
        if text is None:
            print(f"error: cannot read slice file {args.slice}")
            return 2
        ids = set(ID_RE.findall(text))
    table_columns, rows, malformed = rows_as_dicts(read(os.path.join(args.rewrite_dir, "ledger.md")))
    errors = structure_errors(table_columns, malformed)
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        return 1
    s = stats(args.rewrite_dir, ids)
    if ids is not None:
        known = {alias for r in rows for alias in r["aliases"]}
        s["unmatched_ids"] = sorted(ids - known)
        if not s["rows"]:
            print("warning: the selection matches no ledger rows; nothing is verified", file=sys.stderr)
        if s["unmatched_ids"]:
            print("warning: not in the ledger: " + ", ".join(s["unmatched_ids"]), file=sys.stderr)
    print(json.dumps(s, indent=2) if args.json else format_stats(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())

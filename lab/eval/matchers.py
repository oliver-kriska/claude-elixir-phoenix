"""Deterministic matcher functions for skill evaluation.

Each matcher returns (passed: bool, evidence: str).
Matchers operate on file content strings or file paths — no LLM calls.
"""

import os
import re
import yaml


def parse_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return {}
    end = content.find("---", 3)
    if end == -1:
        return {}
    try:
        return yaml.safe_load(content[3:end]) or {}
    except yaml.YAMLError:
        return {}


def get_body(content: str) -> str:
    """Get markdown body (everything after frontmatter)."""
    if not content.startswith("---"):
        return content
    end = content.find("---", 3)
    if end == -1:
        return content
    return content[end + 3:].strip()


def get_sections(content: str) -> dict[str, str]:
    """Parse markdown into {heading: body} dict. Handles ## and ### headings."""
    body = get_body(content)
    sections = {}
    current_heading = None
    current_lines = []

    for line in body.split("\n"):
        if line.startswith("## ") or line.startswith("### "):
            if current_heading is not None:
                sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = line.lstrip("#").strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_heading is not None:
        sections[current_heading] = "\n".join(current_lines).strip()

    return sections


# --- Section matchers ---

def section_exists(content: str, section: str, **_) -> tuple[bool, str]:
    """Check that a markdown section (## or ###) with given name exists."""
    sections = get_sections(content)
    # Case-insensitive match
    found = any(s.lower() == section.lower() for s in sections)
    if found:
        return True, f"Section '{section}' found"
    available = list(sections.keys())[:10]
    return False, f"Section '{section}' not found. Available: {available}"


def section_order(content: str, expected_order: list[str], **_) -> tuple[bool, str]:
    """Check that sections appear in the expected order."""
    sections = list(get_sections(content).keys())
    sections_lower = [s.lower() for s in sections]
    positions = []
    for expected in expected_order:
        try:
            pos = sections_lower.index(expected.lower())
            positions.append(pos)
        except ValueError:
            return False, f"Section '{expected}' not found"
    if positions == sorted(positions):
        return True, "Sections in correct order"
    return False, f"Sections out of order: {[expected_order[i] for i in range(len(positions)) if i > 0 and positions[i] < positions[i-1]]}"


def max_section_lines(content: str, max: int = 40, **_) -> tuple[bool, str]:
    """Check that no section exceeds max lines."""
    sections = get_sections(content)
    violations = []
    for name, body in sections.items():
        line_count = len(body.split("\n"))
        if line_count > max:
            violations.append(f"{name} ({line_count} lines)")
    if not violations:
        return True, f"All sections under {max} lines"
    return False, f"Sections exceeding {max} lines: {', '.join(violations)}"


# --- Content matchers ---

def content_present(content: str, pattern: str, **_) -> tuple[bool, str]:
    """Check that a regex pattern exists in the content."""
    if re.search(pattern, content):
        return True, f"Pattern '{pattern}' found"
    return False, f"Pattern '{pattern}' not found"


def content_absent(content: str, pattern: str, **_) -> tuple[bool, str]:
    """Check that a regex pattern does NOT exist in the content."""
    match = re.search(pattern, content)
    if match:
        return False, f"Pattern '{pattern}' found at: ...{match.group()}..."
    return True, f"Pattern '{pattern}' correctly absent"


def grep_count(content: str, pattern: str, min: int = 0, max: int = 999, **_) -> tuple[bool, str]:
    """Count regex matches and check against min/max bounds."""
    matches = re.findall(pattern, content)
    count = len(matches)
    if min <= count <= max:
        return True, f"Pattern '{pattern}': {count} matches (range {min}-{max})"
    return False, f"Pattern '{pattern}': {count} matches (expected {min}-{max})"


# --- Size matchers ---

def line_count(content: str, target: int = 100, tolerance: int = 85, skill_path: str = "", **_) -> tuple[bool, str]:
    """Check file line count is within target +/- tolerance.

    Score is based on proximity to target. Under target is always good.
    Over target is penalized proportionally.
    """
    if skill_path and os.path.isfile(skill_path):
        with open(skill_path) as f:
            lines = len(f.readlines())
    else:
        lines = len(content.split("\n"))

    if lines <= target:
        return True, f"{lines} lines (target: {target})"
    if lines <= target + tolerance:
        return True, f"{lines} lines (within tolerance: {target}+{tolerance})"
    return False, f"{lines} lines (exceeds target+tolerance: {target}+{tolerance}={target + tolerance})"


def token_estimate(content: str, max_tokens: int = 500, **_) -> tuple[bool, str]:
    """Rough token estimate (words / 0.75). Check body only."""
    body = get_body(content)
    words = len(body.split())
    tokens = int(words / 0.75)
    if tokens <= max_tokens:
        return True, f"~{tokens} tokens (max: {max_tokens})"
    return False, f"~{tokens} tokens (exceeds max: {max_tokens})"


# --- Frontmatter matchers ---

def frontmatter_field(content: str, field: str, expected: str | None = None, **_) -> tuple[bool, str]:
    """Check that a frontmatter field exists and optionally matches expected value."""
    fm = parse_frontmatter(content)
    if field not in fm:
        return False, f"Frontmatter field '{field}' missing"
    if expected is not None and str(fm[field]) != str(expected):
        return False, f"Frontmatter '{field}': got '{fm[field]}', expected '{expected}'"
    return True, f"Frontmatter '{field}': '{fm[field]}'"


def description_length(content: str, min: int = 50, max: int = 300, **_) -> tuple[bool, str]:
    """Check frontmatter description length is in sweet spot."""
    fm = parse_frontmatter(content)
    desc = fm.get("description", "")
    if isinstance(desc, str):
        length = len(desc)
    else:
        length = len(str(desc))
    if min <= length <= max:
        return True, f"Description length: {length} chars (range {min}-{max})"
    return False, f"Description length: {length} chars (expected {min}-{max})"


def description_keywords(content: str, min: int = 5, keywords: list[str] | None = None, **_) -> tuple[bool, str]:
    """Check description has enough domain-specific keywords."""
    fm = parse_frontmatter(content)
    desc = str(fm.get("description", "")).lower()

    if keywords:
        found = [kw for kw in keywords if kw.lower() in desc]
    else:
        # Domain keywords — includes Elixir/Phoenix terms and skill-specific verbs
        # Excludes only trivially generic words (do, use, pattern)
        domain_keywords = [
            "elixir", "phoenix", "liveview", "ecto", "oban", "genserver", "plug",
            "migration", "changeset", "schema", "query", "preload", "pubsub",
            "component", "mount", "handle_event", "handle_info", "assign",
            "stream", "socket", "router", "controller", "context", "repo",
            "exunit", "mox", "factory", "credo", "dialyzer",
            "security", "auth", "session", "token", "deploy", "docker", "fly",
            "debug", "investigate", "audit", "review", "plan", "verify",
            "refactor", "performance", "optimize", "n+1", "iron law",
            "test", "workflow", "constraint", "pr comment",
        ]
        found = [kw for kw in domain_keywords if kw in desc]

    if len(found) >= min:
        return True, f"{len(found)} keywords found (min: {min}): {found[:8]}"
    return False, f"{len(found)} keywords found (min: {min}): {found}"


def description_no_vague(content: str, forbidden: list[str] | None = None, **_) -> tuple[bool, str]:
    """Check description doesn't have vague words. Uses word boundaries to avoid false positives."""
    fm = parse_frontmatter(content)
    desc = str(fm.get("description", "")).lower()
    vague = forbidden or ["general", "various", "etc", "sometimes", "might", "possibly"]
    found = [w for w in vague if re.search(r'\b' + re.escape(w) + r'\b', desc)]
    if not found:
        return True, "No vague words in description"
    return False, f"Vague words in description: {found}"


# --- Cross-reference matchers ---

def valid_skill_refs(content: str, plugin_root: str = "", **_) -> tuple[bool, str]:
    """Check all /phx: or skill name references point to existing skills."""
    if not plugin_root:
        # Try to find plugin root relative to common paths
        for candidate in [
            "plugins/elixir-phoenix",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "plugins", "elixir-phoenix"),
        ]:
            if os.path.isdir(os.path.join(candidate, "skills")):
                plugin_root = candidate
                break

    if not plugin_root or not os.path.isdir(os.path.join(plugin_root, "skills")):
        return False, "Cannot locate plugin root — skill ref check requires plugin_root"

    skills_dir = os.path.join(plugin_root, "skills")
    existing_skills = set(os.listdir(skills_dir))

    # Find /phx: references
    refs = re.findall(r'/phx:(\w[\w-]*)', content)
    # Find skill name references in backticks
    refs += re.findall(r'`(\w[\w-]+)`\s+skill', content)

    missing = []
    for ref in set(refs):
        # Normalize: phx:n1-check -> n1-check
        skill_name = ref.replace("phx:", "")
        if skill_name not in existing_skills:
            # Try common aliases
            aliases = {
                "n1": "n1-check", "assigns": "assigns-audit",
                "lv:assigns": "assigns-audit", "ecto:n1-check": "n1-check",
            }
            if skill_name not in aliases.values():
                missing.append(ref)

    if not missing:
        return True, f"All {len(set(refs))} skill references valid"
    return False, f"Missing skills: {missing}"


def valid_agent_refs(content: str, plugin_root: str = "", **_) -> tuple[bool, str]:
    """Check all agent references point to existing agents."""
    if not plugin_root:
        for candidate in [
            "plugins/elixir-phoenix",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "plugins", "elixir-phoenix"),
        ]:
            if os.path.isdir(os.path.join(candidate, "agents")):
                plugin_root = candidate
                break

    if not plugin_root or not os.path.isdir(os.path.join(plugin_root, "agents")):
        return False, "Cannot locate plugin root — agent ref check requires plugin_root"

    agents_dir = os.path.join(plugin_root, "agents")
    existing_agents = {f.replace(".md", "") for f in os.listdir(agents_dir) if f.endswith(".md")}

    # Find agent references: subagent_type: "name" or agent name in backticks
    refs = re.findall(r'subagent_type[=:]\s*["\']?(\w[\w-]+)', content)
    refs += re.findall(r'`(\w[\w-]+-(?:reviewer|analyzer|architect|validator|runner|specialist|advisor|judge|supervisor|orchestrator|researcher|tracer))`', content)

    # Built-in Claude Code agent types (not in plugin agents/ dir)
    builtin_agents = {"general-purpose", "Explore", "Plan", "code-simplifier"}

    missing = []
    for ref in set(refs):
        if ref in builtin_agents:
            continue
        # Strip elixir-phoenix: prefix if present
        clean_ref = ref.replace("elixir-phoenix:", "")
        if clean_ref not in existing_agents and clean_ref.replace("_", "-") not in existing_agents:
            missing.append(ref)

    if not missing:
        checked = len(set(refs))
        return True, f"All {checked} agent references valid" if checked else "No agent references found"
    return False, f"Missing agents: {missing}"


def valid_file_refs(content: str, skill_path: str = "", **_) -> tuple[bool, str]:
    """Check ${CLAUDE_SKILL_DIR}/references/ paths point to existing files.

    Only checks paths prefixed with ${CLAUDE_SKILL_DIR} (own skill's references).
    Cross-skill references (e.g., compound-docs/references/schema.md) are skipped.
    """
    # Find cross-skill references first (e.g., compound-docs/references/schema.md)
    # These have a skill-name prefix before references/
    cross_skill_filenames = set()
    for match in re.finditer(r'([\w-]+)/references/([\w-]+\.md)', content):
        prefix = match.group(1)
        filename = match.group(2)
        # If prefix is not CLAUDE_SKILL_DIR placeholder, it's a cross-skill ref
        if prefix not in ("CLAUDE_SKILL_DIR}", "CLAUDE_SKILL_DIR"):
            cross_skill_filenames.add(filename)

    # Find own-skill references: ${CLAUDE_SKILL_DIR}/references/ or bare references/
    own_refs = re.findall(r'(?:CLAUDE_SKILL_DIR\}?/)?references/([\w-]+\.md)', content)

    # Filter out cross-skill references
    refs = [r for r in set(own_refs) if r not in cross_skill_filenames]
    if not refs:
        return True, "No own-skill reference file paths found"

    if not skill_path:
        return False, "No skill_path provided — file ref check requires skill_path"

    skill_dir = os.path.dirname(skill_path)
    missing = []
    for ref in refs:
        full_path = os.path.join(skill_dir, "references", ref)
        if not os.path.isfile(full_path):
            missing.append(f"references/{ref}")

    if not missing:
        return True, f"All {len(refs)} reference file paths valid"
    return False, f"Missing reference files: {missing}"


# --- Safety matchers ---

def has_iron_laws(content: str, min_count: int = 1, **_) -> tuple[bool, str]:
    """Check Iron Laws section exists and has content.

    If multiple sections match, uses the one with the most items
    (handles cases where a code example contains a template Iron Laws heading).
    """
    sections = get_sections(content)
    best_count = 0
    found_any = False

    for name, body in sections.items():
        if "iron law" in name.lower():
            found_any = True
            items = re.findall(r'^\s*(?:\d+[\.\)]\s+|[-*]\s+)', body, re.MULTILINE)
            if len(items) > best_count:
                best_count = len(items)

    if not found_any:
        return False, "No Iron Laws section found"

    if best_count >= min_count:
        return True, f"Iron Laws section has {best_count} items (min: {min_count})"
    return False, f"Iron Laws section has {best_count} items (min: {min_count})"


def no_dangerous_patterns(content: str, patterns: list[str] | None = None, **_) -> tuple[bool, str]:
    """Check content doesn't contain dangerous code patterns in examples.

    Skips Iron Laws sections where anti-patterns are documented as warnings.
    """
    dangerous = patterns or [
        r'raw\(/1',
        r'String\.to_atom\(',
        r'MIX_ENV=prod',
        r'\|\s*raw\b',
    ]

    # Get body, excluding:
    # 1. Iron Laws sections (anti-patterns documented as warnings)
    # 2. Anti-pattern table rows (| bad_pattern | good_pattern |)
    sections = get_sections(content)
    filtered_lines = []
    for name, body in sections.items():
        skip_sections = ("iron law", "anti-pattern", "red flag", "detection", "checklist", "vulnerabilit", "confidence level")
        if any(kw in name.lower() for kw in skip_sections):
            continue
        for line in body.split("\n"):
            # Skip table rows showing bad→good pattern comparisons
            if line.strip().startswith("|") and "|" in line[1:]:
                continue
            filtered_lines.append(line)
    check_text = "\n".join(filtered_lines)

    found = []
    for pattern in dangerous:
        if re.search(pattern, check_text):
            found.append(pattern)

    if not found:
        return True, "No dangerous patterns found"
    return False, f"Dangerous patterns found: {found}"


# --- Clarity & Specificity matchers (from SkillsBench, MePO papers) ---

def action_density(content: str, min_ratio: float = 0.4, **_) -> tuple[bool, str]:
    """Measure ratio of actionable lines to total non-empty lines.

    Actionable lines start with imperative verbs, numbered steps, bullet items,
    code blocks, or table rows. Theory/context lines are everything else.
    From MePO: Clarity + Precision are the dominant quality merits.
    From SkillsBench: detailed > comprehensive — actionable content wins.
    """
    body = get_body(content)
    lines = [line.strip() for line in body.split("\n") if line.strip()]

    # Skip headings, blank lines, code fence markers
    content_lines = [line for line in lines if not line.startswith("#") and line not in ("```", "---")]
    if not content_lines:
        return True, "No content lines to analyze"

    imperative_verbs = r'^(?:Run|Add|Create|Check|Read|Use|Set|Write|Install|Configure|Start|Stop|Enable|Disable|Remove|Delete|Update|Fix|Move|Copy|Spawn|Load|Save|Open|Close|Verify|Test|Build|Deploy|Review|Merge|Commit|Push|Pull|Execute|Invoke|Call|Apply|Import|Export|Send|Fetch|Parse|Search|Find|List|Show|Print|Log|Debug|Skip|Avoid|Replace|Extract|Generate|Validate|Ensure|Include|Exclude|Prefer|Always|Never|Do not|MUST|NEVER|CRITICAL)\b'

    actionable = 0
    for line in content_lines:
        if re.match(imperative_verbs, line, re.IGNORECASE):
            actionable += 1
        elif re.match(r'^\s*\d+[\.\)]\s+', line):  # Numbered steps
            actionable += 1
        elif re.match(r'^\s*[-*]\s+\*\*', line):  # Bold bullet items
            actionable += 1
        elif line.startswith("|") and "|" in line[1:]:  # Table rows
            actionable += 1

    ratio = actionable / len(content_lines) if content_lines else 0
    if ratio >= min_ratio:
        return True, f"Action density: {ratio:.0%} ({actionable}/{len(content_lines)} lines actionable, min: {min_ratio:.0%})"
    return False, f"Action density: {ratio:.0%} ({actionable}/{len(content_lines)} lines actionable, min: {min_ratio:.0%})"


def specificity_ratio(content: str, min_ratio: float = 0.3, **_) -> tuple[bool, str]:
    """Measure ratio of concrete patterns to vague guidance.

    Concrete: code blocks, file paths, command examples, specific function names.
    Vague: "consider", "you may want to", "it depends", "as needed".
    From SkillsBench: Specificity dimension is critical for skill effectiveness.
    """
    body = get_body(content)
    lines = [line.strip() for line in body.split("\n") if line.strip() and not line.startswith("#")]
    if not lines:
        return True, "No content lines to analyze"

    # Concrete indicators
    concrete_patterns = [
        r'`[^`]+`',           # Inline code
        r'^\s*\|',            # Table rows
        r'\w+\.\w+\.\w+',    # Dotted paths (Module.function.arity)
        r'/\w+[/\w]*\.\w+',  # File paths
        r'mix \w+',           # Mix commands
        r'--\w+',             # CLI flags
        r'\w+_\w+\.ex',      # Elixir file names
        r'^\s*-\s*\[\s*\]',  # Checklist items (- [ ])
        r'^\s*\d+\.\s*\*\*', # Bold numbered items (1. **Rule**)
    ]
    # Vague indicators
    vague_phrases = [
        r'\b(?:consider|you may want|it depends|as needed|if necessary|when appropriate)\b',
        r'\b(?:should probably|might want to|could potentially|try to|attempt to)\b',
        r'\b(?:in some cases|depending on|for example you could)\b',
    ]

    # Count lines with concrete vs vague indicators.
    # Use binary per-line detection (has concrete? yes/no) to avoid
    # sensitivity to content within code blocks — only structure matters.
    # This prevents gaming via variable renames (EST perturbation robustness).
    concrete_count = 0
    vague_count = 0
    in_code_block = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            # Code block delimiters count as concrete (structure indicator)
            concrete_count += 1
            continue
        if in_code_block:
            # All code block lines count as concrete (one per line, content-agnostic)
            concrete_count += 1
            continue
        has_concrete = any(re.search(p, line) for p in concrete_patterns)
        has_vague = any(re.search(p, line, re.IGNORECASE) for p in vague_phrases)
        if has_concrete:
            concrete_count += 1
        if has_vague:
            vague_count += 1

    total = concrete_count + vague_count
    if total == 0:
        return True, "No specificity indicators found (neutral)"
    ratio = concrete_count / len(lines)
    if ratio >= min_ratio:
        return True, f"Specificity: {ratio:.0%} concrete ({concrete_count} concrete, {vague_count} vague, {len(lines)} total)"
    return False, f"Specificity: {ratio:.0%} concrete ({concrete_count} concrete, {vague_count} vague, min: {min_ratio:.0%})"


def has_examples(content: str, min_blocks: int = 1, min_lines: int = 2, **_) -> tuple[bool, str]:
    """Check for code examples (fenced blocks) of sufficient length.

    From SkillsBench: Examples dimension (0-3 scale) — presence and quality of working examples.
    """
    body = get_body(content)
    blocks = re.findall(r'```[\w]*\n(.*?)```', body, re.DOTALL)
    substantial = [b for b in blocks if len(b.strip().split("\n")) >= min_lines]

    if len(substantial) >= min_blocks:
        return True, f"{len(substantial)} code examples found (min: {min_blocks}, each >= {min_lines} lines)"
    return False, f"{len(substantial)} code examples with >= {min_lines} lines (min: {min_blocks})"


def no_duplication(content: str, ngram_size: int = 5, max_dupes: int = 3, **_) -> tuple[bool, str]:
    """Detect repeated instructional phrases across different sections.

    Finds n-gram phrases (5+ words) that appear in multiple sections.
    Filters out: code blocks, reference paths, table rows, common patterns.
    From SkillsBench: Conciseness matters — repeated instructions waste context.
    """
    sections = get_sections(content)
    if len(sections) < 2:
        return True, "Only 1 section — no cross-section duplication possible"

    # Build ngrams per section, excluding code blocks, tables, and reference paths
    section_ngrams: dict[str, set[tuple]] = {}
    for name, body in sections.items():
        # Skip References sections (repeated paths are expected)
        if "reference" in name.lower():
            continue
        # Remove code blocks and table rows before extracting ngrams
        filtered_lines = []
        in_code_block = False
        for line in body.split("\n"):
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            if line.strip().startswith("|"):
                continue
            # Skip lines that are just file paths
            if re.match(r'^[-*]\s*`?\$?\{?.*references/', line):
                continue
            filtered_lines.append(line)

        text = " ".join(filtered_lines)
        words = re.findall(r'\w+', text.lower())
        ngrams = set()
        for i in range(len(words) - ngram_size + 1):
            ngram = tuple(words[i:i + ngram_size])
            ngrams.add(ngram)
        section_ngrams[name] = ngrams

    # Find ngrams appearing in 2+ sections
    all_dupes = []
    section_names = list(section_ngrams.keys())
    stopwords = {"the", "a", "is", "in", "to", "for", "of", "with", "and", "or", "this", "that", "if", "on", "it", "by", "from", "not", "be", "are", "you", "your"}
    for i in range(len(section_names)):
        for j in range(i + 1, len(section_names)):
            shared = section_ngrams[section_names[i]] & section_ngrams[section_names[j]]
            # Filter: at least 2 non-stopwords in the ngram
            meaningful = [ng for ng in shared
                         if sum(1 for w in ng if w not in stopwords) >= 3]
            if meaningful:
                all_dupes.extend(meaningful[:2])  # Cap per pair

    unique_dupes = set(all_dupes)
    if len(unique_dupes) <= max_dupes:
        return True, f"{len(unique_dupes)} duplicated phrases (max: {max_dupes})"
    examples = [" ".join(ng) for ng in list(unique_dupes)[:3]]
    return False, f"{len(unique_dupes)} duplicated phrases (max: {max_dupes}), e.g.: {examples}"


def negative_triggers(content: str, **_) -> tuple[bool, str]:
    """Check description includes negative triggers (when NOT to use).

    From Anthropic docs: descriptions should say when to use AND when NOT to use.
    From SkillsBench: explicit constraints improve triggering accuracy.
    """
    fm = parse_frontmatter(content)
    desc = str(fm.get("description", "")).lower()
    negative_patterns = [
        r'\bnot\s+for\b', r'\bskip\s+for\b', r'\bnot\s+when\b',
        r'\bdo\s+not\s+use\b', r'\bnever\s+use\b', r'\bavoid\b',
        r'\binstead\s+use\b', r'\bdon\'t\s+use\b', r'\bnot\s+suitable\b',
    ]
    found = [p for p in negative_patterns if re.search(p, desc)]
    if found:
        return True, f"Description has negative triggers ({len(found)} patterns)"
    return False, "No negative triggers in description (missing 'NOT for X' or 'Skip for X')"


def workflow_step_coverage(content: str, **_) -> tuple[bool, str]:
    """Check that command skills with numbered steps have all steps present.

    Detects "Step 1", "Step 2", etc. and verifies no gaps in numbering.
    From SkillsBench: Completeness includes workflow coverage.
    """
    body = get_body(content)
    steps = re.findall(r'Step\s+(\d+)', body)
    if not steps:
        return True, "No numbered steps found (not a workflow skill)"

    step_nums = sorted(set(int(s) for s in steps))
    if not step_nums:
        return True, "No numbered steps"

    # Check for gaps
    expected = list(range(step_nums[0], step_nums[-1] + 1))
    missing = [s for s in expected if s not in step_nums]
    if not missing:
        return True, f"Steps {step_nums[0]}-{step_nums[-1]} all present ({len(step_nums)} steps)"
    return False, f"Missing steps: {missing} (found: {step_nums})"


def description_structure(content: str, **_) -> tuple[bool, str]:
    """Check description has both 'what it does' AND 'when to use it' components.

    From Anthropic's official guide: descriptions need action verb + domain + trigger scenarios.
    """
    fm = parse_frontmatter(content)
    desc = str(fm.get("description", ""))
    if not desc:
        return False, "No description found"

    has_what = bool(re.search(r'^[A-Z][a-z]+\s', desc))  # Starts with action verb
    # Accept synonyms: Use/Employ/Apply/Invoke when... (EST robustness)
    has_when = bool(re.search(r'\b(?:[Uu]se|[Ee]mploy|[Aa]pply|[Ii]nvoke)\s+(?:when|after|for|to|ONLY)\b', desc))

    if has_what and has_when:
        return True, "Description has 'what' + 'when' components"
    missing = []
    if not has_what:
        missing.append("'what it does' (start with action verb)")
    if not has_when:
        missing.append("'when to use' (Use when/after/for...)")
    return False, f"Description missing: {', '.join(missing)}"


# --- Matcher registry ---

MATCHERS = {
    "section_exists": section_exists,
    "section_order": section_order,
    "max_section_lines": max_section_lines,
    "content_present": content_present,
    "content_absent": content_absent,
    "grep_count": grep_count,
    "line_count": line_count,
    "token_estimate": token_estimate,
    "frontmatter_field": frontmatter_field,
    "description_length": description_length,
    "description_keywords": description_keywords,
    "description_no_vague": description_no_vague,
    "valid_skill_refs": valid_skill_refs,
    "valid_agent_refs": valid_agent_refs,
    "valid_file_refs": valid_file_refs,
    "has_iron_laws": has_iron_laws,
    "no_dangerous_patterns": no_dangerous_patterns,
    # New: Clarity & Specificity (from SkillsBench, MePO, Anthropic docs)
    "action_density": action_density,
    "specificity_ratio": specificity_ratio,
    "has_examples": has_examples,
    "no_duplication": no_duplication,
    "negative_triggers": negative_triggers,
    "workflow_step_coverage": workflow_step_coverage,
    "description_structure": description_structure,
}


def run_check(content: str, check_type: str, skill_path: str = "", plugin_root: str = "", **params) -> tuple[bool, str]:
    """Run a single check by type name. Returns (passed, evidence)."""
    matcher = MATCHERS.get(check_type)
    if matcher is None:
        return False, f"Unknown check type: {check_type}"
    return matcher(content, skill_path=skill_path, plugin_root=plugin_root, **params)

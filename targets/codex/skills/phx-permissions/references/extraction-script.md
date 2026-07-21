# Session JSONL Extraction Script

Run this Python script to extract all uncovered Bash commands from recent sessions:

```python
python3 -c "
import json, os, glob, fnmatch, re
from datetime import datetime
from collections import Counter

DAYS = ${DAYS:-14}

# 1. Read current allowed patterns from all settings files
allowed = []
for path in [os.path.expanduser('~/.claude/settings.json'),
             '.claude/settings.json', '.claude/settings.local.json']:
    try:
        with open(path) as f:
            allowed.extend(json.load(f).get('permissions',{}).get('allow',[]))
    except: pass

# 2. Build matchers from permission patterns
# Handles both formats:
#   Bash(git *)   — current (space before wildcard)
#   Bash(git:*)   — deprecated (colon before wildcard)
#   Bash(git status) — exact match
#   Bash          — matches ALL bash commands
def make_glob(perm):
    if perm == 'Bash' or perm == 'Bash(*)':
        return '*'  # matches everything
    m = re.match(r'Bash\((.+)\)', perm)
    if not m: return None
    pat = m.group(1)
    # Normalize deprecated :* to space *
    if pat.endswith(':*'):
        pat = pat[:-2] + ' *'
    return pat

pats = [make_glob(p) for p in allowed if p.startswith('Bash')]
pats = [p for p in pats if p]

def is_covered(cmd):
    return any(fnmatch.fnmatch(cmd, p) for p in pats)

# 3. Scan ALL project JSONL files from last N days
all_files = glob.glob(os.path.expanduser('~/.claude/projects/*/*.jsonl'))
cutoff = datetime.now().timestamp() - DAYS*86400
recent = [f for f in all_files if os.path.getmtime(f) > cutoff]

uncovered = Counter()
examples = {}
deprecated = []
for fp in recent:
    try:
        with open(fp) as f:
            for line in f:
                entry = json.loads(line)
                if entry.get('type') != 'assistant': continue
                for block in (entry.get('message',{}).get('content',[]) or []):
                    if not isinstance(block, dict): continue
                    if block.get('type') == 'tool_use' and block.get('name') == 'Bash':
                        cmd = block.get('input',{}).get('command','').strip().split(chr(10))[0][:300]
                        if cmd and not is_covered(cmd):
                            parts = cmd.split()
                            base = ' '.join(parts[:2]) if len(parts)>=2 else parts[0]
                            uncovered[base] += 1
                            if base not in examples:
                                examples[base] = cmd[:120]
    except: pass

# 4. Check for deprecated :* patterns in current settings
for p in allowed:
    if p.startswith('Bash(') and ':*)' in p:
        deprecated.append(p)

# 5. Output results
print(f'Sessions scanned: {len(recent)} (last {DAYS} days)')
print(f'Uncovered command patterns: {len(uncovered)}')
print(f'Total avoidable prompts: {sum(uncovered.values())}')
if deprecated:
    print(f'Deprecated :* patterns to fix: {len(deprecated)}')
print()
for cmd, count in uncovered.most_common(30):
    ex = examples.get(cmd,'')
    print(f'{count:4d}x  {cmd}')
    if ex != cmd: print(f'       e.g.: {ex[:100]}')
if deprecated:
    print(f'\n=== DEPRECATED :* patterns (replace : with space) ===')
    for p in deprecated[:10]:
        print(f'  {p}  ->  {p.replace(chr(58)+chr(42)+chr(41), chr(32)+chr(42)+chr(41))}')
    if len(deprecated) > 10:
        print(f'  ... and {len(deprecated)-10} more')
"
```

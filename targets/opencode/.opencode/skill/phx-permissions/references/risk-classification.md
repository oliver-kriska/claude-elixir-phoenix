# Risk Classification Rules

Comprehensive command classification for the permission analyzer.

## Classification Algorithm

1. Extract the **base command** (first token or first two tokens for compound commands)
2. Check against RED list first (deny-list takes priority)
3. Check against GREEN list
4. Default to YELLOW if not in either list

## GREEN — Read-Only and Standard Dev Tools

Commands that cannot cause data loss or security issues.

### Always Safe

| Pattern | Rationale |
|---------|-----------|
| `ls *` | Read-only directory listing |
| `cat *` | Read-only file content |
| `head *`, `tail *` | Read-only file content |
| `wc *` | Read-only counting |
| `find *` | Read-only file search |
| `grep *`, `rg *` | Read-only content search |
| `which *`, `where *` | Read-only path lookup |
| `echo *` | Output only |
| `date`, `whoami`, `pwd` | Info only |
| `file *` | Read-only type detection |
| `diff *` | Read-only comparison |

### Elixir/Phoenix Safe

| Pattern | Rationale |
|---------|-----------|
| `mix compile *` | Build step, reversible |
| `mix test *` | Read-only test execution |
| `mix format --check-formatted *` | Read-only check |
| `mix credo *` | Read-only analysis |
| `mix hex.info *` | Read-only package info |
| `mix hex.audit` | Read-only security check |
| `mix deps.audit` | Read-only dependency check |
| `mix xref *` | Read-only cross-reference |
| `mix dialyzer *` | Read-only type check |
| `mix phx.routes *` | Read-only route listing |
| `elixir -e *` | Evaluation (treat as GREEN for simple expressions) |
| `iex -S mix` | Interactive shell |

### Git Read-Only

| Pattern | Rationale |
|---------|-----------|
| `git status *` | Read-only |
| `git log *` | Read-only |
| `git diff *` | Read-only |
| `git show *` | Read-only |
| `git branch` (no -D/-d) | Read-only listing |
| `git remote -v` | Read-only |
| `git stash list` | Read-only |

### Node/Frontend Safe

| Pattern | Rationale |
|---------|-----------|
| `node -e *` | Evaluation |
| `npx prettier --check *` | Read-only |
| `npm ls *` | Read-only |
| `npm outdated` | Read-only |

## YELLOW — Write Operations (Recommend with Caution)

Commands that modify local state but are generally recoverable.

### Git Write Operations

| Pattern | Note |
|---------|------|
| `git add *` | Stages files (reversible with reset) |
| `git commit *` | Creates commit (reversible with reset) |
| `git push` (no --force) | Publishes commits |
| `git checkout *` | Switches branches, can discard changes |
| `git switch *` | Switches branches |
| `git stash *` | Saves/restores work |
| `git merge *` | Merges branches |
| `git rebase *` (no --force) | Rewrites history locally |
| `git branch -d *` | Deletes merged branch |

### Elixir Write Operations

| Pattern | Note |
|---------|------|
| `mix format *` (without --check) | Modifies files (reversible via git) |
| `mix deps.get` | Downloads dependencies |
| `mix deps.compile *` | Compiles dependencies |
| `mix ecto.migrate` | Runs migrations (has rollback) |
| `mix ecto.rollback` | Rolls back migration |
| `mix ecto.gen.migration *` | Creates migration file |
| `mix phx.gen.* *` | Generates code files |
| `mix ecto.setup` | Creates + migrates + seeds |

### File Operations

| Pattern | Note |
|---------|------|
| `mkdir *` | Creates directories |
| `touch *` | Creates empty files |
| `cp *` | Copies files |
| `mv *` | Moves files (reversible if in git) |

### Package Managers

| Pattern | Note |
|---------|------|
| `npm install *` | Installs packages |
| `npm run *` | Runs scripts |
| `yarn *` | Package operations |
| `hex.pm` commands | Package operations |

## RED — Never Auto-Allow

Commands that can cause irreversible damage, security risks, or
affect systems beyond the local project.

### Destructive Operations

| Pattern | Risk |
|---------|------|
| `rm *` | File deletion (irreversible outside git) |
| `rm -rf *` | Recursive deletion |
| `rmdir *` | Directory deletion |
| `mix ecto.reset` | Drops + recreates database |
| `mix ecto.drop` | Drops database |
| `git push --force *` | Overwrites remote history |
| `git push -f *` | Overwrites remote history |
| `git reset --hard *` | Discards uncommitted changes |
| `git clean -f *` | Deletes untracked files |
| `git branch -D *` | Force-deletes branch |

### Privilege Escalation

| Pattern | Risk |
|---------|------|
| `sudo *` | Elevated privileges |
| `su *` | User switching |
| `chmod 777 *` | World-writable permissions |
| `chown *` | Ownership changes |

### Network / External

| Pattern | Risk |
|---------|------|
| `curl * \| sh` | Remote code execution |
| `wget * \| sh` | Remote code execution |
| `curl * \| bash` | Remote code execution |
| `ssh *` | Remote access |
| `scp *` | Remote file transfer |

### Process Control

| Pattern | Risk |
|---------|------|
| `kill *` | Process termination |
| `killall *` | Mass process termination |
| `pkill *` | Pattern-based process kill |

### Container / Infrastructure

| Pattern | Risk |
|---------|------|
| `docker rm *` | Container deletion |
| `docker rmi *` | Image deletion |
| `docker system prune *` | Mass cleanup |

## Edge Cases

### Compound Commands

For piped or chained commands (`cmd1 | cmd2`, `cmd1 && cmd2`):

- Classify EACH component separately
- Final classification = highest risk component
- `mix test | head` → GREEN (both GREEN)
- `mix deps.get && rm -rf _build` → RED (rm is RED)

### Commands with Redirects

- `echo "text" > file.txt` → YELLOW (file write)
- `cat file > /dev/null` → GREEN (null write is safe)

### Environment Variables

- `MIX_ENV=test mix test` → Same as `mix test` (GREEN)
- `MIX_ENV=prod mix phx.server` → RED (production operations)
- `DATABASE_URL=... mix ecto.*` → YELLOW (external DB connection)

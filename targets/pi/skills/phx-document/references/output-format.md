# Documentation Output Format

Write documentation report to `.claude/plans/{slug}/reviews/{feature}-docs.md`:

```markdown
# Documentation: {Feature}

## Generated Documentation

### @moduledoc Added

| Module | Description |
|--------|-------------|
| `MyApp.Auth` | Authentication context |
| `MyApp.Auth.MagicToken` | Magic token schema |

### @doc Added

| Function | Module |
|----------|--------|
| `create_magic_token/1` | MyApp.Auth |
| `verify_magic_token/1` | MyApp.Auth |

### README Updated

- Added "Magic Link Authentication" section

### ADR Created

- `docs/adr/003-magic-link-auth.md`

## Documentation Checklist

- [x] All new modules have @moduledoc
- [x] All public functions have @doc
- [x] README updated for user-facing features
- [x] ADR created for architectural decisions
```

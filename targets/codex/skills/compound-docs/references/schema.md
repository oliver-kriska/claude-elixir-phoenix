# Compound Documentation Schema

YAML frontmatter schema for solution documentation files.

## Required Fields

### module

- **Type**: string
- **Description**: Elixir module or context area
- **Examples**: `"Accounts"`, `"LiveView.UserList"`, `"Workers.EmailSender"`

### date

- **Type**: string
- **Pattern**: `YYYY-MM-DD`

### problem_type

- **Type**: string
- **Description**: Category of the problem. Use a concise label.
- **Suggested values**: `build_error`, `test_failure`, `runtime_error`,
  `performance_issue`, `database_issue`, `security_issue`,
  `liveview_bug`, `oban_issue`, `otp_issue`, `integration_issue`,
  `logic_error`, `deployment_issue`, `iron_law_violation`
- Free-form — use the closest match or create a new label if needed.

### component

- **Type**: string
- **Description**: Which component area was affected.
- **Suggested values**: `ecto_schema`, `ecto_query`, `ecto_migration`,
  `phoenix_context`, `phoenix_controller`, `phoenix_router`,
  `liveview_mount`, `liveview_events`, `liveview_components`,
  `liveview_streams`, `oban_worker`, `oban_config`, `genserver`,
  `supervisor`, `pubsub`, `authentication`, `authorization`,
  `testing`, `deployment`, `configuration`
- Free-form — use the closest match or create a new label if needed.

### symptoms

- **Type**: array of strings (1-5 items)
- **Description**: Observable symptoms — error messages, visual issues,
  unexpected behavior. Must be specific and observable.
- **Examples**:
  - `"** (Ecto.Association.NotLoaded) association :posts not loaded"`
  - `"LiveView process terminated with :timeout"`

### root_cause

- **Type**: string
- **Description**: The actual underlying reason WHY this happened.
  Be specific and descriptive. Use the cause, not the symptom.
- **Examples**: `"missing preload on :posts association"`,
  `"blocking database query in disconnected LiveView mount"`,
  `"atom keys in Oban job args instead of string keys"`

### severity

- **Type**: enum
- **Values**: `critical`, `high`, `medium`, `low`

### tags

- **Type**: array of strings (up to 8)
- **Description**: Searchable keywords, lowercase, hyphen-separated
- **Examples**: `["preload", "association", "n-plus-one"]`

## Optional Fields

### elixir_version / phoenix_version

- **Type**: string, pattern `X.Y.Z`

### iron_law_number

- **Type**: integer (1-13)
- **Description**: Which Iron Law was violated (if applicable)

### related_solutions

- **Type**: array of strings (file paths to related solutions)

## Validation Rules

1. `module` must be a valid Elixir module or context name
2. `date` must be in `YYYY-MM-DD` format
3. `symptoms` must be specific and observable (not vague)
4. `root_cause` must explain WHY, not just WHAT
5. `severity` must be one of the four enum values
6. `tags` should be lowercase, hyphen-separated

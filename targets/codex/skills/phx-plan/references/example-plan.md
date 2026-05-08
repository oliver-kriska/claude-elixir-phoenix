# Example Plan Output

For `/phx:plan Add user profile avatars`:

```markdown
# Plan: User Profile Avatars

**Status**: PENDING
**Created**: 2024-01-15
**Detail Level**: more
**Input**: from description

## Summary

Add avatar upload to user profiles with S3 storage, automatic resizing,
and LiveView drag-drop upload with progress indicator.

## Scope

**In Scope:**

- Avatar upload via LiveView
- S3 storage with Waffle
- Automatic resizing to 3 sizes
- Default avatar fallback

**Out of Scope:**

- Animated GIFs
- Avatar cropping UI

## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Upload library | Waffle | Existing S3 config, team familiar |
| Image processing | Image | Pure Elixir, no native deps |
| Resize strategy | Oban worker | Non-blocking, retryable |

## Data Model

alter table(:users) do
  add :avatar, :string  # S3 key
end

## Phase 1: Setup & Storage [PENDING]

- [ ] [P1-T1][direct] Add dependencies and configure S3
  **Locations**: mix.exs, config/runtime.exs
  **Implementation**: Add `{:waffle, "~> 1.1"}`,
  `{:waffle_ecto, "~> 0.0.12"}`, `{:image, "~> 0.42"}`.
  Configure Waffle for S3 in runtime.exs using existing
  `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` env vars.
  Follow pattern from `config/runtime.exs:45`.

- [ ] [P1-T2][ecto] Create migration and update schema
  **Implementation**: Add avatar string field to users table.
  Update User schema with `field :avatar, :string`.
  Add AvatarUploader module using `use Waffle.Definition`
  with versions: `:original`, `:medium` (300x300),
  `:thumb` (100x100).

## Phase 2: Upload & Resize [PENDING]

- [ ] [P2-T1][oban] Create async resize worker
  **Implementation**: Create `AvatarResizeWorker` using
  `use Oban.Worker, queue: :media`. On perform, download
  original from S3, resize with Image library, upload
  versions back. Follow `EmailWorker` pattern.
  **Pattern**:
  ```elixir
  def perform(%Oban.Job{args: %{"user_id" => id}}) do
    user = Accounts.get_user!(id)
    # download, resize, upload versions
  end
  ```

- [ ] [P2-T2][liveview] Build upload LiveView with drag-drop
  **Implementation**: Create AvatarUploadLive component
  using `allow_upload/3` with `:avatar` field. Add drag-drop
  zone with progress indicator. On save, upload to S3 and
  enqueue resize job. Add to user settings page.
  Follow `ProductImageLive` upload pattern.
  **Locations**: lib/app_web/live/avatar_upload_live.ex,
  lib/app_web/live/user_settings_live.html.heex

- [ ] [P2-T3][direct] Create AvatarDisplay function component
  **Implementation**: Render avatar URL from User struct with
  fallback to default Gravatar-style generated avatar.
  Accept `:size` attr (`:thumb`, `:medium`, `:original`).

## Phase 3: Tests [PENDING]

- [ ] [P3-T1][test] Unit and integration tests
  **Implementation**: Test AvatarUploader versions, Oban
  worker with Mox-ed S3, LiveView upload flow with
  `file_input/3` and `render_upload/3`. Mock S3 with Mox.
  **Locations**: test/app/accounts_test.exs,
  test/app/workers/avatar_resize_worker_test.exs,
  test/app_web/live/avatar_upload_live_test.exs

## Patterns to Follow

- S3 config pattern from `config/runtime.exs:45`
- LiveView upload pattern from `ProductImageLive`
- Oban worker pattern from `EmailWorker`

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Large file uploads timeout | Chunked upload with progress |
| S3 credentials in test | Mock S3 with Mox |

## Verification Checklist

- [ ] `mix compile --warnings-as-errors` passes
- [ ] `mix format --check-formatted` passes
- [ ] `mix credo --strict` passes
- [ ] `mix test` passes
- [ ] Upload works in browser
- [ ] Images resize correctly

```

Note how tasks are grouped by logical work unit (not per-file),
each includes implementation detail, and locations are listed
within tasks rather than as separate tasks.

---

## Example with System Map (Breadboarding)

For `/phx:plan Add real-time project kanban board`:

This example shows a multi-page LiveView feature where
breadboarding adds value. The System Map captures Places,
affordances, and wiring before task generation.

```markdown
# Plan: Project Kanban Board

**Status**: PENDING
**Created**: 2024-02-20
**Detail Level**: comprehensive
**Input**: from description

## Summary

Add a real-time kanban board to projects with drag-drop cards,
column management, and multi-user live updates via PubSub.

## Scope

**In Scope:**

- Kanban board LiveView with draggable cards
- Column CRUD (add, rename, reorder)
- Card creation, editing, assignment
- Real-time multi-user updates

**Out of Scope:**

- Card comments/attachments
- Board templates
- Swimlanes

## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Drag-drop | JS hook + SortableJS | LiveView needs JS for drag |
| Card ordering | `:integer` position field | Simple, reorderable |
| Real-time | PubSub per board | Scoped updates, not global |

## Data Model

```elixir
# boards table
add :name, :string
add :project_id, references(:projects)

# columns table
add :title, :string
add :position, :integer
add :board_id, references(:boards)

# cards table (existing tasks table, add column_id)
add :column_id, references(:columns)
add :position, :integer
```

## System Map

### Places

| ID | Place | Entry Point | Notes |
|----|-------|-------------|-------|
| P1 | BoardLive | `/projects/:id/board` | Main kanban view |
| P2 | CardFormModal | click card or "+" | Modal over P1 |
| P3 | ColumnHeaderEdit | double-click column title | Inline edit mode |

### UI Affordances

| ID | Place | Component | Affordance | Type | Wires Out | Returns To |
|----|-------|-----------|------------|------|-----------|------------|
| U1 | P1 | column | "+" card button | phx-click | N1 | - |
| U2 | P1 | column | card list | stream | - | from S1 |
| U3 | P1 | card | drag handle | JS hook | N5 | - |
| U4 | P2 | form | title input | phx-change | N2 | - |
| U5 | P2 | form | assignee select | phx-change | N2 | - |
| U6 | P2 | form | "Save" button | phx-submit | N3 | - |
| U7 | P1 | header | "Add Column" btn | phx-click | N7 | - |
| U8 | P3 | input | column title | phx-submit | N8 | - |

### Code Affordances

| ID | Place | Module | Affordance | Wires Out | Returns To |
|----|-------|--------|------------|-----------|------------|
| N1 | P1 | BoardLive | handle_event("new_card", col_id) | open P2 | S2 |
| N2 | P2 | CardFormModal | handle_event("validate") | - | U4 errors |
| N3 | P2 | CardFormModal | handle_event("save") | N4, close P2 | - |
| N4 | - | Projects | create_card(attrs) | N6 | S3 |
| N5 | P1 | BoardLive | handle_event("reorder") via JS hook | N9 | - |
| N6 | - | Projects | broadcast(:card_created, card) | N10 | - |
| N7 | P1 | BoardLive | handle_event("add_column") | N11 | - |
| N8 | P3 | BoardLive | handle_event("rename_column") | N12 | - |
| N9 | - | Projects | update_card_position(id, col, pos) | N6 | S3 |
| N10 | P1 | BoardLive | handle_info({:card_created, c}) | - | S1 |
| N11 | - | Projects | create_column(board, attrs) | N13 | S3 |
| N12 | - | Projects | update_column(col, attrs) | N13 | S3 |
| N13 | P1 | BoardLive | handle_info({:board_updated}) | - | S1 |

### Data Stores

| ID | Store | Type | Read By | Written By |
|----|-------|------|---------|------------|
| S1 | :cards stream (per column) | stream | U2 | N10, N13 |
| S2 | :card_form assign | assign | U4, U5 | N1, N2 |
| S3 | boards/columns/cards tables | ecto | N4, N9, N11, N12 | N4, N9, N11, N12 |

### Spikes

- None — SortableJS hook pattern verified in codebase

## Phase 1: Data Layer [PENDING]

(covers: S3 — schemas and context functions)

- [ ] [P1-T1][ecto] Create board/column schemas and migrations
  **Implementation**: Board belongs_to Project, Column
  belongs_to Board with position field, add column_id and
  position to existing cards/tasks table.

- [ ] [P1-T2][direct] Add Projects context functions
  **Implementation**: `create_column/2`, `update_column/2`,
  `create_card/2`, `update_card_position/3`, `list_board/1`
  (preloads columns + cards ordered by position). Add PubSub
  broadcast on every write. Follow existing context patterns.

## Phase 2: Board View [PENDING]

(covers: P1, U2, U7, N7, N10, N11, N13, S1 — the read path + columns)

- [ ] [P2-T1][liveview] Build BoardLive with column streams
  **Implementation**: Mount loads board with columns and cards.
  Stream cards per column. Subscribe to board PubSub topic in
  connected mount. Handle column add and board_updated info.
  **Locations**: lib/app_web/live/board_live.ex

## Phase 3: Card Management [PENDING]

(covers: P2, U1, U4-U6, N1-N4, N6, S2 — the write path)

- [ ] [P3-T1][liveview] Build CardFormModal live component
  **Implementation**: Modal with form for title, description,
  assignee. Validate on change, save on submit. Broadcast
  card_created on success, close modal.
  **Locations**: lib/app_web/live/card_form_modal.ex

## Phase 4: Drag-Drop [PENDING]

(covers: U3, N5, N9 — the reorder path)

- [ ] [P4-T1][liveview] Add SortableJS hook for card drag-drop
  **Implementation**: JS hook with SortableJS that pushes
  "reorder" event with card_id, new_column_id, new_position.
  Handle in BoardLive, call update_card_position, broadcast.
  **Locations**: assets/js/hooks/sortable.js,
  lib/app_web/live/board_live.ex

## Phase 5: Tests [PENDING]

- [ ] [P5-T1][test] Context, LiveView, and real-time tests
  **Implementation**: Test create/reorder in Projects context.
  Test BoardLive mount, card creation flow, PubSub updates
  between two connected sessions.
  **Locations**: test/app/projects_test.exs,
  test/app_web/live/board_live_test.exs

## Patterns to Follow

- PubSub pattern from existing real-time features
- Modal pattern from existing live components
- Stream pattern from product listing

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Drag-drop race conditions | Optimistic UI + server reconcile |
| Stream ordering after reorder | Re-stream affected column |

## Verification Checklist

- [ ] `mix compile --warnings-as-errors` passes
- [ ] `mix format --check-formatted` passes
- [ ] `mix credo --strict` passes
- [ ] `mix test` passes
- [ ] Drag-drop works across columns
- [ ] Two browsers see real-time updates

```

Note how the System Map tables directly drove task generation:
each phase maps to a vertical slice through the affordance
tables, and phase comments reference which IDs they cover.

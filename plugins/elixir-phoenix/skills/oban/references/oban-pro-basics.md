# Oban Pro Reference

Oban Pro extends Oban with advanced worker types, job composition, and operational plugins.

> **Official docs**: <https://oban.pro/docs/pro/overview.html>
> Always check for the latest API — this reference covers stable core features.

## Migration: OSS to Pro

### Worker Migration

| OSS Oban | Oban Pro |
|----------|----------|
| `use Oban.Worker` | `use Oban.Pro.Worker` |
| `@impl Oban.Worker` | `@impl Oban.Pro.Worker` |
| `def perform(%Job{})` | `def process(%Job{})` |
| `Oban.Testing` | `Oban.Pro.Testing` |
| Advisory lock engine | `Oban.Pro.Engines.Smart` |

### Plugin Migration

Pro plugins **enhance** OSS equivalents (same base features + extras).
Swap the module name — do NOT run both simultaneously:

| OSS Plugin | Pro Enhancement | Key Addition |
|------------|----------------|-------------|
| `Plugins.Cron` | `DynamicCron` | Runtime CRUD, missed job guarantees, per-entry timezone |
| `Plugins.Lifeline` | `DynamicLifeline` | Auto-repairs stuck workflows/chains, producer-based rescue |
| `Plugins.Pruner` | `DynamicPruner` | Per-queue/worker/state retention policies, before_delete hook |

### Engine Migration

```elixir
# config/config.exs — switch to Smart Engine
config :my_app, Oban,
  engine: Oban.Pro.Engines.Smart,
  repo: MyApp.Repo,
  queues: [default: 10]
```

Smart Engine enables: global concurrency, distributed rate limiting, async tracking.

---

## Pro.Worker Features

Pro.Worker replaces `perform/1` with `process/1` and adds optional features:
structured args, hooks, encryption, deadlines, chaining, and recorded output.

Without `args_schema`, Pro.Worker works identically to OSS — just use `process/1`
with string-key pattern matching instead of `perform/1`.

### Structured Jobs (`args_schema`) — Optional

Opt-in type-safe args with compile-time validation and casting.
When used, `process/1` receives a struct instead of a raw map:

```elixir
defmodule MyApp.Workers.SendEmail do
  use Oban.Pro.Worker, queue: :mailers

  args_schema do
    field :email, :string, required: true
    field :user_id, :id, required: true
    field :priority, :enum, values: ~w(low normal high)a, default: :normal

    embeds_one :config do
      field :subject, :string
      field :template, :string
    end
  end

  @impl Oban.Pro.Worker
  def process(%Job{args: %__MODULE__{email: email, config: config}}) do
    MyApp.Mailer.send(email, config.subject, config.template)
  end
end
```

Supported types: `:id`, `:integer`, `:string`, `:float`, `:boolean`,
`:binary`, `:map`, `:enum`, `:uuid`, `:datetime_utc`.

### Recorded Jobs

Store job output for retrieval by downstream jobs or dashboards:

```elixir
use Oban.Pro.Worker, recorded: true

@impl Oban.Pro.Worker
def process(%Job{} = job) do
  result = MyApp.expensive_computation(job.args)
  {:ok, result}  # Automatically recorded, compressed
end
```

### Encrypted Jobs

AES-256-CTR encryption for args at rest:

```elixir
use Oban.Pro.Worker,
  encryption: {MyApp.Vault, :fetch_key, []}
```

**Iron Law**: Encryption breaks uniqueness on `args` (encrypted args differ
each time). Use `meta` for unique constraints with encrypted workers.

### Deadlines

Preemptively cancel jobs exceeding time limits:

```elixir
use Oban.Pro.Worker, deadline: {1, :hour}

# Or per-job:
MyApp.Worker.new(%{data: "..."}, deadline: {30, :minutes})
```

### Chaining

Enforce sequential execution per partition key:

```elixir
use Oban.Pro.Worker, chain: [by: [args: :account_id]]

@impl Oban.Pro.Worker
def process(%Job{args: %{"account_id" => _aid}}) do
  # Only one job with this account_id runs at a time
  :ok
end
```

Partition options: `:worker`, `[args: :field]`, `[meta: :key]`.

### Worker Hooks

Lifecycle callbacks: `before_new/1`, `before_process/1`, `after_process/2`,
`on_cancelled/1`, `on_discarded/1`. Use for logging, metrics, Sentry integration.

```elixir
def after_process(%Job{} = job, _result), do: Metrics.track(:job_done, %{worker: job.worker})
def on_discarded(%Job{} = job), do: alert_team(job)
```

### Worker Aliases

Rename workers without breaking queued jobs: `aliases: [MyApp.OldWorkerName]`

---

## Job Composition Patterns

### When to Use What

| Pattern | Use When |
|---------|----------|
| **Workflow** | Multi-step with dependencies (ETL, pipelines) |
| **Batch** | Many parallel jobs, need aggregate callbacks |
| **Chunk** | Bulk processing for efficiency (SMS, notifications) |
| **Relay** | Need synchronous job result |
| **Chain** | Sequential per partition key (per-account ordering) |

### Workflows

Compose jobs with arbitrary dependencies (sequential, fan-out, fan-in):

```elixir
alias Oban.Pro.Workflow

Workflow.new()
|> Workflow.add(:extract, ExtractWorker.new(%{source: "api"}))
|> Workflow.add(:transform, TransformWorker.new(%{}), deps: [:extract])
|> Workflow.add(:validate, ValidateWorker.new(%{}), deps: [:transform])
|> Workflow.add(:load, LoadWorker.new(%{}), deps: [:validate])
|> Oban.insert_all()
```

Access upstream results with recorded jobs:

```elixir
# In LoadWorker:
def process(%Job{} = job) do
  {:ok, data} = Oban.Pro.Workflow.get_recorded(job, :transform)
  load_data(data)
end
```

### Batches

Group parallel jobs with aggregate lifecycle callbacks.

> **Note**: Batch API varies between Oban Pro versions. Check your installed
> version's docs with `mix hex.docs online oban_pro` for exact callback pattern.

```elixir
defmodule MyApp.EmailBatch do
  use Oban.Pro.Worker, queue: :mailers

  @impl Oban.Pro.Worker
  def process(%Job{args: %{"email" => email}}) do
    MyApp.Mailer.send(email)
  end

  # Batch lifecycle callbacks — check Oban.Pro.Batch docs for your version
  def batch_completed(_job), do: Logger.info("All emails sent!")
  def batch_exhausted(_job), do: alert_team("Batch had failures")
end
```

Common callbacks: `batch_attempted/1`, `batch_completed/1`, `batch_cancelled/1`,
`batch_discarded/1`, `batch_exhausted/1`.

### Chunks

Process jobs atomically in groups for efficiency:

```elixir
defmodule MyApp.SmsSender do
  use Oban.Pro.Workers.Chunk,
    queue: :messages,
    size: 100,
    timeout: 5_000

  @impl true
  def process(jobs) do
    jobs
    |> Enum.map(& &1.args)
    |> MyApp.SMS.send_batch()
  end
end
```

Note: `process/1` receives a **list** of jobs, not a single job.

### Relay

Synchronous job execution: `Oban.Pro.Relay.async/1` + `Relay.await/2`.
Useful for: distributed task results, API endpoints needing job output, testing.

---

## Smart Engine

The Smart Engine replaces advisory locks with index-backed operations,
enabling multi-node features:

```elixir
config :my_app, Oban,
  engine: Oban.Pro.Engines.Smart,
  queues: [
    default: [local_limit: 10, global_limit: 50],
    api_calls: [
      local_limit: 5,
      rate_limit: [allowed: 100, period: 60]
    ]
  ]
```

### Key Capabilities

- **Global concurrency**: `global_limit` caps total jobs across all nodes
- **Rate limiting**: `rate_limit` with algorithms: `:sliding_window`, `:fixed_window`, `:token_bucket`
- **Partitioning**: Segment limits by worker, args, or metadata
- **Async tracking**: Batched status updates for throughput

Also provides `Oban.Pro.RateLimit` for programmatic rate limit checks outside jobs.

### Smart Engine Gotchas

**One partition limiter per queue**: Only ONE of `global_limit` or `rate_limit`
can have `partition` on a given queue. If you need both user isolation AND
rate limiting, use `rate_limit` with partition (provides both):

```elixir
# WRONG — two limiters with partition on same queue
my_queue: [
  global_limit: [allowed: 1, partition: [args: :user_id]],
  rate_limit: [allowed: 1, period: 60, partition: [args: :user_id]]
]

# CORRECT — rate_limit provides both isolation and throttling
my_queue: [
  local_limit: 200,
  rate_limit: [allowed: 1, period: 60, partition: [args: :user_id]]
]
```

**Snooze rolls back attempt counter**: With Smart Engine, `{:snooze, seconds}`
does NOT increment `attempt`. Code guarding on `attempt` to limit snoozes
will loop infinitely. Use `meta["snoozed"]` instead:

```elixir
# WRONG — infinite loop! Smart Engine resets attempt on snooze
def process(%Job{attempt: attempt}) when attempt <= 3 do
  {:snooze, 5}
end

# CORRECT — track snooze count in meta
def process(%Job{meta: meta} = job) do
  snoozed = Map.get(meta, "snoozed", 0)
  if snoozed < 3, do: {:snooze, 5}, else: {:cancel, "Max snoozes reached"}
end
```

---

## Pro Plugins

Pro-only plugins (no OSS equivalent):

| Plugin | Purpose |
|--------|---------|
| `DynamicQueues` | Runtime queue CRUD, node-specific routing |
| `DynamicPrioritizer` | Auto-bumps priority for starved jobs |
| `DynamicScaler` | Auto-scale infrastructure by queue depth |

### DynamicCron Example

```elixir
plugins: [
  {Oban.Pro.Plugins.DynamicCron, crontab: [
    {"0 0 * * *", MyApp.DailyReportWorker},
    {"0 */6 * * *", MyApp.SyncWorker, timezone: "America/New_York"}
  ]}
]
```

Runtime management: insert/update/delete cron entries without redeployment.

### DynamicQueues

Runtime queue management: `insert/3`, `update/3`, `delete/2` for CRUD without redeployment.
Supports node-specific routing via `only:` option.

---

## Anti-patterns

```elixir
# --- Wrong callback name (silent no-op!) ---
# BAD: perform/1 in Pro worker
def perform(%Job{} = job), do: process_data(job)
# GOOD: process/1 in Pro worker
def process(%Job{} = job), do: process_data(job)

# --- Encrypted args with unique on args ---
# BAD: uniqueness on encrypted fields (won't match!)
use Oban.Pro.Worker, encryption: [...], unique: [keys: [:user_id]]
# GOOD: use meta for uniqueness with encryption
use Oban.Pro.Worker, encryption: [...], unique: [keys: [], meta: [:user_id]]

# --- Chunk process/1 expects list ---
# BAD: pattern matching single job in chunk worker
def process(%Job{args: args}), do: ...
# GOOD: pattern matching list of jobs
def process(jobs) when is_list(jobs), do: ...
```

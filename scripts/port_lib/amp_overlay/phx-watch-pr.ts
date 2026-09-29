// Generated into targets/amp/plugins/phx-watch-pr.ts. Edit this canonical source.

import { createHash } from 'node:crypto'
import { execFile } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'
import type {
  PluginAPI,
  PluginThread,
  Subscription,
  ThreadMessage,
  WebhookEvent,
  WebhookHandlerContext,
} from '@ampcode/plugin'

export const description =
  'Keeps an Amp worker orb awake while required PR checks and review threads are pending; never merges or deploys.'

const stateKey = 'elixirPhoenixWatchPrState'
const stateVersion = 1
const defaultPollIntervalMs = 60_000
const defaultQuietPeriodMs = 15 * 60_000
const defaultMaxDurationMs = 2 * 60 * 60_000
const minPollIntervalMs = 30_000
const maxPollIntervalMs = 5 * 60_000
const minQuietPeriodMs = 5 * 60_000
const maxQuietPeriodMs = 60 * 60_000
const minMaxDurationMs = 30 * 60_000
const maxMaxDurationMs = 24 * 60 * 60_000
const webhookProbeMs = 2 * 60_000
const maxConsecutiveErrors = 5
const fixTurnTimeoutMs = 30 * 60_000
const maxReviewPages = 10
const deploymentCheck =
  /(?:^|[^a-z0-9])(?:deploy(?:ment|ments)?|release|preview|production|prod|tag[_\s-]*version)(?:$|[^a-z0-9])/i
const acceptedWebhookEvents = new Set([
  'check_run',
  'check_suite',
  'issue_comment',
  'pull_request',
  'pull_request_review',
  'pull_request_review_comment',
  'pull_request_review_thread',
  'status',
])

type WatchStatus =
  | 'active'
  | 'succeeded'
  | 'timed_out'
  | 'error'
  | 'closed'
  | 'stopped'

type CheckBucket = 'pass' | 'fail' | 'pending' | 'skipping' | 'cancel'

interface CheckState {
  key: string
  name: string
  workflow: string
  bucket: CheckBucket
  state: string
  link: string
}

interface ReviewThreadState {
  id: string
  author: string
  body: string
  path: string
  line: number | null
  url: string
  outdated: boolean
}

interface PRSnapshot {
  repo: string
  pr: number
  url: string
  state: string
  draft: boolean
  headSha: string
  latestReviewActivityAt: string
  reviewActivityHash: string
  requiredChecks: CheckState[]
  excludedChecks: CheckState[]
  unresolvedThreads: ReviewThreadState[]
}

interface ReviewState {
  unresolvedThreads: ReviewThreadState[]
  latestActivityAt: string
  activityHash: string
}

interface PersistedWatch {
  key: string
  repo: string
  pr: number
  url: string
  threadID: PluginThread['id']
  checksOnly: boolean
  fix: boolean
  pollIntervalMs: number
  quietPeriodMs: number
  maxDurationMs: number
  startedAt: number
  deadlineAt: number
  status: WatchStatus
  terminalReason?: string
  terminalAt?: number
  readySince?: number
  consecutiveErrors: number
  lastSnapshot?: PRSnapshot
  lastSnapshotHash?: string
  lastReadinessHash?: string
  lastNotifiedHash?: string
  pendingFixHash?: string
  fixInFlightHash?: string
  lastFixHash?: string
  reactivationProbeUntil?: number
}

interface WatchStore {
  version: number
  watches: Record<string, PersistedWatch>
  recentWebhookIDs: string[]
}

interface GhResult {
  code: number
  stdout: string
  stderr: string
}

interface CheckRow {
  name?: unknown
  workflow?: unknown
  bucket?: unknown
  state?: unknown
  link?: unknown
}

interface PullRequestIdentity {
  repo?: string
  pr: number
}

const reviewThreadsQuery = `
query($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      comments(last: 100) {
        nodes { id createdAt updatedAt }
      }
      reviews(last: 100) {
        nodes { id submittedAt }
      }
      reviewThreads(first: 100, after: $cursor) {
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          comments(last: 50) {
            nodes {
              id
              url
              body
              createdAt
              updatedAt
              author { login }
            }
          }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}`

function emptyStore(): WatchStore {
  return { version: stateVersion, watches: {}, recentWebhookIDs: [] }
}

function hash(value: unknown): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex')
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function clip(value: unknown, limit: number): string {
  const text = typeof value === 'string' ? value.replace(/\s+/g, ' ').trim() : ''
  return text.length <= limit ? text : `${text.slice(0, limit - 1)}…`
}

function integerInRange(
  value: unknown,
  fallback: number,
  minimum: number,
  maximum: number,
  multiplier: number,
): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) return fallback
  const converted = Math.round(value * multiplier)
  return Math.min(maximum, Math.max(minimum, converted))
}

function parsePRInput(value: string): PullRequestIdentity {
  const input = value.trim()
  if (/^\d+$/.test(input)) return { pr: Number(input) }
  const match = input.match(
    /^https?:\/\/[^/]+\/([^/]+)\/([^/]+)\/pull\/(\d+)(?:[/?#].*)?$/,
  )
  if (!match) throw new Error('Use a PR number or a GitHub pull request URL.')
  return { repo: `${match[1]}/${match[2].replace(/\.git$/, '')}`, pr: Number(match[3]) }
}

function normalizeRepo(value: string): string {
  const repo = value.trim().replace(/^https?:\/\/[^/]+\//, '').replace(/\.git$/, '')
  if (!/^[^/\s]+\/[^/\s]+$/.test(repo)) {
    throw new Error('Repository must use OWNER/NAME format.')
  }
  return repo
}

function runGh(args: string[]): Promise<GhResult> {
  return new Promise((resolve) => {
    execFile(
      'gh',
      args,
      {
        encoding: 'utf8',
        env: { ...process.env, GH_PAGER: 'cat', NO_COLOR: '1' },
        maxBuffer: 4_000_000,
        timeout: 12_000,
      },
      (error, stdout, stderr) => {
        const rawCode = error && 'code' in error ? error.code : 0
        resolve({
          code: typeof rawCode === 'number' ? rawCode : error ? 1 : 0,
          stdout: String(stdout ?? ''),
          stderr: String(stderr ?? ''),
        })
      },
    )
  })
}

async function currentRepo(): Promise<string> {
  const result = await runGh(['repo', 'view', '--json', 'nameWithOwner', '--jq', '.nameWithOwner'])
  if (result.code !== 0 || !result.stdout.trim()) {
    throw new Error(`Could not identify the current GitHub repository: ${clip(result.stderr, 240)}`)
  }
  return normalizeRepo(result.stdout)
}

function normalizeBucket(bucket: unknown, state: unknown): CheckBucket {
  const known = String(bucket ?? '').toLowerCase()
  if (['pass', 'fail', 'pending', 'skipping', 'cancel'].includes(known)) {
    return known as CheckBucket
  }
  const raw = String(state ?? '').toUpperCase()
  if (['SUCCESS', 'PASS', 'PASSED', 'NEUTRAL', 'SKIPPED', 'SKIPPING'].includes(raw)) {
    return raw.startsWith('SKIP') ? 'skipping' : 'pass'
  }
  if (
    [
      'FAIL',
      'FAILED',
      'FAILURE',
      'ERROR',
      'TIMED_OUT',
      'ACTION_REQUIRED',
      'STALE',
    ].includes(raw)
  ) return 'fail'
  if (['CANCEL', 'CANCELED', 'CANCELLED'].includes(raw)) return 'cancel'
  return 'pending'
}

function checkState(row: CheckRow): CheckState {
  const name = String(row.name ?? 'unnamed check')
  const workflow = String(row.workflow ?? '')
  const state = String(row.state ?? 'UNKNOWN')
  const link = String(row.link ?? '')
  return {
    key: `${workflow}\u0000${name}\u0000${link}`,
    name,
    workflow,
    state,
    link,
    bucket: normalizeBucket(row.bucket, state),
  }
}

function parsePlainChecks(stdout: string): CheckState[] {
  return stdout
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const columns = line.split('\t')
      return checkState({
        name: columns[0],
        state: columns[1],
        link: columns.find((column) => /^https?:\/\//.test(column)) ?? '',
      })
    })
}

async function fetchChecks(repo: string, pr: number, required: boolean): Promise<CheckState[]> {
  const base = ['pr', 'checks', String(pr), '--repo', repo]
  if (required) base.push('--required')
  const jsonResult = await runGh([
    ...base,
    '--json',
    'name,state,bucket,link,workflow',
  ])
  if (/no (?:required )?checks reported/i.test(jsonResult.stderr)) return []
  if (jsonResult.stdout.trim()) {
    try {
      const rows = JSON.parse(jsonResult.stdout)
      if (Array.isArray(rows)) return rows.map((row) => checkState(row as CheckRow))
    } catch {
      // Older gh versions do not support JSON for `pr checks`; use stable tabular output.
    }
  }
  if (!/unknown flag.*--json|unknown shorthand flag|accepts? .* arg/i.test(jsonResult.stderr)) {
    throw new Error(`Could not read PR checks: ${clip(jsonResult.stderr, 300)}`)
  }
  const plainResult = await runGh(base)
  if (/no (?:required )?checks reported/i.test(plainResult.stderr)) return []
  if (!plainResult.stdout.trim() && plainResult.code !== 0) {
    throw new Error(`Could not read PR checks: ${clip(plainResult.stderr, 300)}`)
  }
  return parsePlainChecks(plainResult.stdout)
}

function latestTimestamp(values: unknown[]): string {
  return values
    .filter((value): value is string =>
      typeof value === 'string' && Number.isFinite(Date.parse(value)),
    )
    .sort()
    .at(-1) ?? ''
}

async function fetchReviewState(repo: string, pr: number): Promise<ReviewState> {
  const [owner, name] = repo.split('/', 2)
  const unresolved: ReviewThreadState[] = []
  const activityTimestamps: unknown[] = []
  const activityRecords: unknown[] = []
  let cursor: string | undefined

  for (let page = 0; page < maxReviewPages; page += 1) {
    const args = [
      'api',
      'graphql',
      '-f',
      `query=${reviewThreadsQuery}`,
      '-F',
      `owner=${owner}`,
      '-F',
      `name=${name}`,
      '-F',
      `number=${pr}`,
    ]
    if (cursor) args.push('-f', `cursor=${cursor}`)
    const result = await runGh(args)
    if (result.code !== 0) {
      throw new Error(`Could not read review threads: ${clip(result.stderr, 300)}`)
    }
    const payload = JSON.parse(result.stdout) as any
    const connection = payload?.data?.repository?.pullRequest?.reviewThreads
    if (!connection || !Array.isArray(connection.nodes)) {
      throw new Error('GitHub returned an invalid review-thread response.')
    }
    const pullRequest = payload.data.repository.pullRequest
    if (!cursor) {
      for (const comment of pullRequest.comments?.nodes ?? []) {
        activityTimestamps.push(comment?.createdAt, comment?.updatedAt)
        activityRecords.push({
          kind: 'comment',
          id: comment?.id,
          createdAt: comment?.createdAt,
          updatedAt: comment?.updatedAt,
        })
      }
      for (const review of pullRequest.reviews?.nodes ?? []) {
        activityTimestamps.push(review?.submittedAt)
        activityRecords.push({
          kind: 'review',
          id: review?.id,
          submittedAt: review?.submittedAt,
        })
      }
    }
    for (const node of connection.nodes) {
      if (!node) continue
      const comments = Array.isArray(node.comments?.nodes) ? node.comments.nodes : []
      for (const comment of comments) {
        activityTimestamps.push(comment?.createdAt, comment?.updatedAt)
        activityRecords.push({
          kind: 'review-thread-comment',
          id: comment?.id,
          createdAt: comment?.createdAt,
          updatedAt: comment?.updatedAt,
        })
      }
      if (node.isResolved) continue
      const latest = comments.at(-1) ?? {}
      unresolved.push({
        id: String(node.id),
        author: String(latest.author?.login ?? 'unknown'),
        body: clip(latest.body, 240),
        path: String(node.path ?? ''),
        line: typeof node.line === 'number' ? node.line : null,
        url: String(latest.url ?? ''),
        outdated: Boolean(node.isOutdated),
      })
    }
    if (!connection.pageInfo?.hasNextPage) break
    cursor = String(connection.pageInfo.endCursor ?? '')
    if (!cursor || page === maxReviewPages - 1) {
      throw new Error('Review-thread pagination exceeded the safe 1,000-thread limit.')
    }
  }

  return {
    unresolvedThreads: unresolved.sort((left, right) => left.id.localeCompare(right.id)),
    latestActivityAt: latestTimestamp(activityTimestamps),
    activityHash: hash(activityRecords.map((record) => JSON.stringify(record)).sort()),
  }
}

function isDeploymentCheck(check: CheckState): boolean {
  return deploymentCheck.test(`${check.workflow} ${check.name}`)
}

function uniqueChecks(checks: CheckState[]): CheckState[] {
  return [...new Map(checks.map((check) => [check.key, check])).values()].sort((a, b) =>
    a.key.localeCompare(b.key),
  )
}

async function fetchSnapshot(
  repo: string,
  pr: number,
  checksOnly: boolean,
): Promise<PRSnapshot> {
  const view = await runGh([
    'pr',
    'view',
    String(pr),
    '--repo',
    repo,
    '--json',
    'number,state,isDraft,headRefOid,url',
  ])
  if (view.code !== 0) {
    throw new Error(`Could not read PR ${repo}#${pr}: ${clip(view.stderr, 300)}`)
  }
  const identity = JSON.parse(view.stdout) as any
  const state = String(identity.state ?? 'UNKNOWN').toUpperCase()
  if (state !== 'OPEN') {
    return {
      repo,
      pr,
      url: String(identity.url ?? ''),
      state,
      draft: Boolean(identity.isDraft),
      headSha: String(identity.headRefOid ?? ''),
      latestReviewActivityAt: '',
      reviewActivityHash: '',
      requiredChecks: [],
      excludedChecks: [],
      unresolvedThreads: [],
    }
  }

  const [required, all, reviewState] = await Promise.all([
    fetchChecks(repo, pr, true),
    fetchChecks(repo, pr, false),
    checksOnly
      ? Promise.resolve<ReviewState>({
        unresolvedThreads: [],
        latestActivityAt: '',
        activityHash: '',
      })
      : fetchReviewState(repo, pr),
  ])
  return {
    repo,
    pr,
    url: String(identity.url ?? ''),
    state,
    draft: Boolean(identity.isDraft),
    headSha: String(identity.headRefOid ?? ''),
    latestReviewActivityAt: reviewState.latestActivityAt,
    reviewActivityHash: reviewState.activityHash,
    requiredChecks: uniqueChecks(required.filter((check) => !isDeploymentCheck(check))),
    excludedChecks: uniqueChecks([
      ...all.filter(isDeploymentCheck),
      ...required.filter(isDeploymentCheck),
    ]),
    unresolvedThreads: reviewState.unresolvedThreads,
  }
}

function snapshotHash(snapshot: PRSnapshot): string {
  return hash(snapshot)
}

function readinessHash(snapshot: PRSnapshot): string {
  return hash({
    state: snapshot.state,
    draft: snapshot.draft,
    headSha: snapshot.headSha,
    latestReviewActivityAt: snapshot.latestReviewActivityAt,
    reviewActivityHash: snapshot.reviewActivityHash,
    requiredChecks: snapshot.requiredChecks,
    unresolvedThreads: snapshot.unresolvedThreads,
  })
}

function failedRequiredChecks(snapshot: PRSnapshot): CheckState[] {
  return snapshot.requiredChecks.filter((check) => ['fail', 'cancel'].includes(check.bucket))
}

function hasActionableEvidence(snapshot: PRSnapshot): boolean {
  return snapshot.unresolvedThreads.length > 0 || failedRequiredChecks(snapshot).length > 0
}

function actionableHash(snapshot: PRSnapshot): string {
  return hash({
    headSha: snapshot.headSha,
    failedChecks: failedRequiredChecks(snapshot),
    unresolvedThreads: snapshot.unresolvedThreads,
  })
}

function fixHash(snapshot: PRSnapshot): string {
  return actionableHash(snapshot)
}

function isReady(snapshot: PRSnapshot): boolean {
  return (
    snapshot.state === 'OPEN' &&
    !snapshot.draft &&
    snapshot.requiredChecks.every((check) =>
      ['pass', 'skipping'].includes(check.bucket),
    ) &&
    snapshot.unresolvedThreads.length === 0
  )
}

function checksLine(checks: CheckState[]): string {
  if (checks.length === 0) return 'Required non-deployment checks: none configured.'
  return `Required non-deployment checks: ${checks
    .map((check) => `${check.workflow ? `${check.workflow} / ` : ''}${check.name}=${check.bucket}`)
    .join(', ')}.`
}

function excludedLine(checks: CheckState[]): string {
  if (checks.length === 0) {
    return 'Excluded deployment/release/preview/production checks: none reported.'
  }
  return `Excluded deployment/release/preview/production checks (not evaluated): ${checks
    .map((check) => `${check.workflow ? `${check.workflow} / ` : ''}${check.name}=${check.bucket}`)
    .join(', ')}.`
}

function reviewLines(threads: ReviewThreadState[]): string[] {
  if (threads.length === 0) return ['Unresolved actionable review threads: 0.']
  return [
    `Unresolved actionable review threads: ${threads.length}.`,
    ...threads.slice(0, 12).map((thread) =>
      `- ${thread.author} at ${thread.path}${thread.line ? `:${thread.line}` : ''}${
        thread.outdated ? ' (outdated)' : ''
      }: ${thread.body || '(no body)'}${thread.url ? ` — ${thread.url}` : ''}`,
    ),
    ...(threads.length > 12 ? [`- …and ${threads.length - 12} more.`] : []),
  ]
}

function failedCheckLines(checks: CheckState[]): string[] {
  if (checks.length === 0) return []
  return [
    `Failed/cancelled required non-deployment checks: ${checks.length}.`,
    ...checks.map((check) =>
      `- ${check.workflow ? `${check.workflow} / ` : ''}${check.name}=${check.bucket}${
        check.link ? ` — ${check.link}` : ''
      }`,
    ),
  ]
}

function actionableLines(snapshot: PRSnapshot): string[] {
  return [
    `${snapshot.repo}#${snapshot.pr}; head ${snapshot.headSha.slice(0, 12) || 'unknown'}.`,
    ...failedCheckLines(failedRequiredChecks(snapshot)),
    ...(snapshot.unresolvedThreads.length > 0 ? reviewLines(snapshot.unresolvedThreads) : []),
  ]
}

function snapshotSummary(snapshot: PRSnapshot): string {
  return [
    `${snapshot.repo}#${snapshot.pr} is ${snapshot.state}${snapshot.draft ? ' (draft)' : ''}; head ${snapshot.headSha.slice(0, 12) || 'unknown'}.`,
    checksLine(snapshot.requiredChecks),
    excludedLine(snapshot.excludedChecks),
    `Latest review/comment activity: ${snapshot.latestReviewActivityAt || 'none observed'}.`,
    ...reviewLines(snapshot.unresolvedThreads),
  ].join('\n')
}

function messageText(message: ThreadMessage): string {
  return message.content
    .filter((block): block is { type: 'text'; text: string } => block.type === 'text')
    .map((block) => block.text)
    .join('\n')
}

async function hasMessageMarker(thread: PluginThread, marker: string): Promise<boolean> {
  for (let offset = 0; offset < 100; offset += 20) {
    const messages = await thread.messages({
      full: true,
      from: 'end',
      offset,
      limit: 20,
      roles: ['user'],
    })
    if (messages.some((message) => messageText(message).includes(marker))) return true
    if (messages.length < 20) return false
  }
  return false
}

function eventMarker(watch: PersistedWatch, kind: string, eventHash: string): string {
  return `[phx-watch-pr:${watch.key}:${kind}:${eventHash}]`
}

function webhookTargets(payload: any): { repo?: string; prs: number[]; headShas: string[] } {
  const repo = typeof payload?.repository?.full_name === 'string'
    ? payload.repository.full_name
    : undefined
  const prValues = [
    payload?.pull_request?.number,
    payload?.issue?.pull_request ? payload?.issue?.number : undefined,
    ...(Array.isArray(payload?.check_run?.pull_requests)
      ? payload.check_run.pull_requests.map((pr: any) => pr?.number)
      : []),
    ...(Array.isArray(payload?.check_suite?.pull_requests)
      ? payload.check_suite.pull_requests.map((pr: any) => pr?.number)
      : []),
  ]
  const shaValues = [
    payload?.sha,
    payload?.pull_request?.head?.sha,
    payload?.check_run?.head_sha,
    payload?.check_suite?.head_sha,
  ]
  return {
    repo,
    prs: [...new Set(prValues.filter((value): value is number => Number.isInteger(value)))],
    headShas: [...new Set(shaValues.filter((value): value is string =>
      typeof value === 'string' && value.length > 0,
    ))],
  }
}

export default function (amp: PluginAPI) {
  let disposed = false
  let storePromise: Promise<WatchStore> | undefined
  let writeQueue: Promise<void> = Promise.resolve()
  const leases = new Map<string, Subscription>()
  const timers = new Map<string, ReturnType<typeof setTimeout>>()
  const messageQueues = new Map<string, Promise<void>>()
  const fixTasks = new Map<string, Promise<void>>()

  const workspace = amp.system.workspaceRoot
    ? amp.helpers.filePathFromURI(amp.system.workspaceRoot)
    : 'no-workspace'
  const webhookDirectory = join(
    process.env.ELIXIR_PHOENIX_WATCH_PR_CREDENTIAL_DIR ??
      join(homedir(), '.config', 'amp', 'phx-watch-pr'),
    hash(workspace).slice(0, 16),
  )
  const webhookCredentialFile = join(webhookDirectory, 'webhook-url')

  async function loadStore(): Promise<WatchStore> {
    if (!storePromise) {
      storePromise = amp.configuration.get().then((configuration) => {
        const raw = configuration[stateKey] as any
        if (raw === undefined) return emptyStore()
        if (
          !raw ||
          raw.version !== stateVersion ||
          !raw.watches ||
          typeof raw.watches !== 'object' ||
          !Array.isArray(raw.recentWebhookIDs)
        ) {
          throw new Error('Persisted phx-watch-pr state is invalid or from an unsupported version.')
        }
        return raw as WatchStore
      })
    }
    return storePromise
  }

  async function persistStore(): Promise<void> {
    const store = await loadStore()
    const durableCopy = JSON.parse(JSON.stringify(store)) as WatchStore
    writeQueue = writeQueue
      .catch(() => undefined)
      .then(() => amp.configuration.update({ [stateKey]: durableCopy }, 'workspace'))
    await writeQueue
  }

  function clearTimer(key: string): void {
    const timer = timers.get(key)
    if (timer) clearTimeout(timer)
    timers.delete(key)
  }

  function releaseLease(key: string): void {
    leases.get(key)?.unsubscribe()
    leases.delete(key)
  }

  async function acquireLease(watch: PersistedWatch): Promise<void> {
    if (disposed || leases.has(watch.key)) return
    const lease = await amp.system.executor.keepAlive()
    if (disposed || watch.status !== 'active') {
      lease.unsubscribe()
      return
    }
    leases.set(watch.key, lease)
  }

  function schedulePoll(key: string, delay: number): void {
    if (disposed) return
    clearTimer(key)
    const timer = setTimeout(async () => {
      timers.delete(key)
      await pollWatch(key)
    }, Math.max(0, delay))
    timers.set(key, timer)
  }

  async function appendOnce(
    watch: PersistedWatch,
    kind: string,
    eventHash: string,
    content: string,
  ): Promise<boolean> {
    const marker = eventMarker(watch, kind, eventHash)
    const thread = amp.threads.get(watch.threadID)
    if (await hasMessageMarker(thread, marker)) return false
    await thread.appendUserMessage(
      { type: 'user-message', content: `${marker}\n${content}` },
      { steer: false },
    )
    return true
  }

  function enqueueMessage(key: string, operation: () => Promise<void>): Promise<void> {
    const queued = (messageQueues.get(key) ?? Promise.resolve())
      .catch(() => undefined)
      .then(operation)
    messageQueues.set(key, queued)
    void queued.finally(() => {
      if (messageQueues.get(key) === queued) messageQueues.delete(key)
    })
    return queued
  }

  async function finishWatch(
    key: string,
    status: Exclude<WatchStatus, 'active'>,
    reason: string,
    notify = true,
  ): Promise<void> {
    const store = await loadStore()
    const watch = store.watches[key]
    if (!watch || watch.status !== 'active') return
    watch.status = status
    watch.terminalReason = reason
    watch.terminalAt = Date.now()
    watch.readySince = undefined
    watch.reactivationProbeUntil = undefined
    clearTimer(key)
    try {
      await persistStore()
    } finally {
      releaseLease(key)
    }
    if (!notify) return
    const summary = watch.lastSnapshot
      ? snapshotSummary(watch.lastSnapshot)
      : 'No successful PR snapshot was recorded.'
    const outcome = status === 'succeeded'
      ? 'READY: required non-deployment checks stayed green and unresolved actionable review threads stayed at zero for the full quiet period.'
      : `INCOMPLETE (${status}): ${reason}`
    await enqueueMessage(key, async () => {
      await appendOnce(
        watch,
        'terminal',
        hash({ status, reason, terminalAt: watch.terminalAt }),
        [
          `phx-watch-pr terminal event for ${watch.repo}#${watch.pr}.`,
          outcome,
          summary,
          'The keep-alive lease is released. Never merge or deploy.',
        ].join('\n'),
      )
    })
  }

  function queueFixTurn(watch: PersistedWatch, snapshot: PRSnapshot): void {
    if (!hasActionableEvidence(snapshot)) return
    const currentFixHash = fixHash(snapshot)
    if (watch.lastFixHash === currentFixHash || watch.fixInFlightHash === currentFixHash) return
    watch.pendingFixHash = currentFixHash
    void persistStore()
    if (fixTasks.has(watch.key)) return

    const task = (async () => {
      while (!disposed) {
        const store = await loadStore()
        const current = store.watches[watch.key]
        const pendingHash = current?.pendingFixHash
        const currentSnapshot = current?.lastSnapshot
        if (
          !current ||
          current.status !== 'active' ||
          !current.fix ||
          !pendingHash ||
          !currentSnapshot
        ) break
        if (current.lastFixHash === pendingHash) {
          current.pendingFixHash = undefined
          await persistStore()
          break
        }
        if (!hasActionableEvidence(currentSnapshot)) {
          current.pendingFixHash = undefined
          current.fixInFlightHash = undefined
          current.lastFixHash = undefined
          await persistStore()
          break
        }

        current.fixInFlightHash = pendingHash
        await persistStore()
        const thread = amp.threads.get(current.threadID)
        let completed = false
        try {
          const threadState = await thread.state.get()
          if (threadState === 'running' || threadState === 'awaiting-approval') {
            await thread.waitForResponse({ timeoutMs: fixTurnTimeoutMs })
          }
          const failedChecks = failedRequiredChecks(currentSnapshot)
          const evidenceKinds = [
            ...(currentSnapshot.unresolvedThreads.length > 0 ? ['review feedback'] : []),
            ...(failedChecks.length > 0 ? ['required CI failures'] : []),
          ].join(' and ')
          const appended = await appendOnce(
            current,
            'fix',
            pendingHash,
            [
              `phx-watch-pr --fix found actionable ${evidenceKinds} on ${current.repo}#${current.pr}.`,
              currentSnapshot.unresolvedThreads.length > 0
                ? 'Load and follow the installed phx-pr-review workflow now. Re-fetch every unresolved thread, validate each comment, fix valid findings, reply, and resolve threads where appropriate.'
                : undefined,
              failedChecks.length > 0
                ? 'Inspect the named checks and linked logs. Determine whether each cause belongs to this PR branch; fix only branch-owned causes, run the narrowest relevant verification, and push the authorized branch update. Do not blindly rerun shared CI or treat infrastructure failures as code fixes.'
                : undefined,
              'This --fix invocation authorizes validated PR-review and branch-owned CI fixes, verification, and pushes. It never authorizes merge, deployment, release, preview, or production actions.',
              ...actionableLines(currentSnapshot),
            ].filter(Boolean).join('\n'),
          )
          if (appended) await thread.waitForResponse({ timeoutMs: fixTurnTimeoutMs })
          completed = true
        } catch (error) {
          amp.logger.log(`phx-watch-pr fix turn failed for ${current.key}`, errorText(error))
        }
        current.fixInFlightHash = undefined
        if (completed) {
          current.lastFixHash = pendingHash
          if (current.pendingFixHash === pendingHash) current.pendingFixHash = undefined
        }
        await persistStore()
        if (!completed) break
        schedulePoll(current.key, 0)
        if (!current.pendingFixHash) break
      }
    })()
    fixTasks.set(watch.key, task)
    void task.finally(() => {
      if (fixTasks.get(watch.key) === task) fixTasks.delete(watch.key)
    })
  }

  async function notifyActionableSnapshot(
    watch: PersistedWatch,
    snapshot: PRSnapshot,
  ): Promise<void> {
    const currentHash = actionableHash(snapshot)
    await enqueueMessage(watch.key, async () => {
      await appendOnce(
        watch,
        'actionable',
        currentHash,
        [
          `phx-watch-pr found actionable evidence on ${watch.repo}#${watch.pr}.`,
          ...actionableLines(snapshot),
          'This watch does not have --fix authorization. Inspect and report the evidence; never merge or deploy.',
        ].join('\n'),
      )
    })
  }

  async function processSnapshot(
    watch: PersistedWatch,
    snapshot: PRSnapshot,
    notify: boolean,
  ): Promise<void> {
    const previousReadinessHash = watch.lastReadinessHash
    const nextSnapshotHash = snapshotHash(snapshot)
    const nextReadinessHash = readinessHash(snapshot)
    const nextActionableHash = actionableHash(snapshot)
    const actionable = hasActionableEvidence(snapshot)
    const relevantChange = previousReadinessHash !== nextReadinessHash
    const now = Date.now()

    watch.lastSnapshot = snapshot
    watch.lastSnapshotHash = nextSnapshotHash
    watch.lastReadinessHash = nextReadinessHash
    watch.consecutiveErrors = 0

    if (watch.reactivationProbeUntil) {
      if (!relevantChange && isReady(snapshot) && now < watch.reactivationProbeUntil) {
        await persistStore()
        schedulePoll(watch.key, Math.min(watch.pollIntervalMs, watch.reactivationProbeUntil - now))
        return
      }
      if (!relevantChange && isReady(snapshot)) {
        watch.status = 'succeeded'
        watch.terminalReason = 'Webhook probe found no relevant change.'
        watch.terminalAt = now
        watch.reactivationProbeUntil = undefined
        await persistStore()
        clearTimer(watch.key)
        releaseLease(watch.key)
        return
      }
      watch.reactivationProbeUntil = undefined
      watch.startedAt = now
      watch.deadlineAt = now + watch.maxDurationMs
    }

    if (snapshot.state !== 'OPEN') {
      await persistStore()
      await finishWatch(
        watch.key,
        'closed',
        `PR state changed to ${snapshot.state}; the watcher did not merge it.`,
      )
      return
    }

    if (isReady(snapshot)) {
      if (!watch.readySince || relevantChange) watch.readySince = now
    } else {
      watch.readySince = undefined
    }
    if (!actionable) {
      watch.lastNotifiedHash = undefined
      if (!watch.fixInFlightHash && !watch.pendingFixHash) watch.lastFixHash = undefined
    }
    await persistStore()

    if (notify && actionable && !watch.fix && watch.lastNotifiedHash !== nextActionableHash) {
      await notifyActionableSnapshot(watch, snapshot)
      watch.lastNotifiedHash = nextActionableHash
      await persistStore()
    }
    if (watch.fix && actionable) {
      queueFixTurn(watch, snapshot)
    }

    if (watch.readySince && now - watch.readySince >= watch.quietPeriodMs) {
      await finishWatch(
        watch.key,
        'succeeded',
        `Ready state remained quiet for ${Math.round(watch.quietPeriodMs / 60_000)} minutes.`,
      )
      return
    }
    schedulePoll(watch.key, watch.pollIntervalMs)
  }

  async function pollWatch(key: string): Promise<void> {
    if (disposed) return
    const store = await loadStore()
    const watch = store.watches[key]
    if (!watch || watch.status !== 'active') {
      clearTimer(key)
      releaseLease(key)
      return
    }
    if (Date.now() >= watch.deadlineAt) {
      await finishWatch(
        key,
        'timed_out',
        `Maximum active watch duration of ${Math.round(watch.maxDurationMs / 3_600_000)} hours elapsed; state is incomplete.`,
      )
      return
    }

    try {
      const snapshot = await fetchSnapshot(watch.repo, watch.pr, watch.checksOnly)
      await processSnapshot(watch, snapshot, true)
    } catch (error) {
      watch.consecutiveErrors += 1
      await persistStore()
      if (watch.consecutiveErrors >= maxConsecutiveErrors) {
        await finishWatch(
          key,
          'error',
          `${maxConsecutiveErrors} consecutive GitHub polling errors: ${clip(errorText(error), 300)}`,
        )
      } else {
        schedulePoll(key, watch.pollIntervalMs)
      }
    }
  }

  async function startWatch(input: Record<string, unknown>, thread: PluginThread): Promise<string> {
    if (typeof input.pr !== 'string' || !input.pr.trim()) {
      throw new Error('`pr` is required when starting a watch.')
    }
    const parsed = parsePRInput(input.pr)
    const repo = normalizeRepo(
      typeof input.repo === 'string' && input.repo.trim()
        ? input.repo
        : parsed.repo ?? await currentRepo(),
    )
    const key = `${repo.toLowerCase()}#${parsed.pr}`
    const store = await loadStore()
    const existing = store.watches[key]
    if (existing?.status === 'active') {
      return [
        `Watch already active for ${repo}#${parsed.pr} in thread ${existing.threadID}.`,
        existing.lastSnapshot ? snapshotSummary(existing.lastSnapshot) : 'No snapshot yet.',
      ].join('\n')
    }

    const snapshot = await fetchSnapshot(repo, parsed.pr, Boolean(input.checksOnly))
    if (snapshot.state !== 'OPEN') {
      return `Watch not started: ${repo}#${parsed.pr} is ${snapshot.state}. No lease was acquired.`
    }
    const now = Date.now()
    const watch: PersistedWatch = {
      key,
      repo,
      pr: parsed.pr,
      url: snapshot.url,
      threadID: thread.id,
      checksOnly: Boolean(input.checksOnly),
      fix: Boolean(input.fix),
      pollIntervalMs: integerInRange(
        input.pollIntervalSeconds,
        defaultPollIntervalMs,
        minPollIntervalMs,
        maxPollIntervalMs,
        1_000,
      ),
      quietPeriodMs: integerInRange(
        input.quietPeriodMinutes,
        defaultQuietPeriodMs,
        minQuietPeriodMs,
        maxQuietPeriodMs,
        60_000,
      ),
      maxDurationMs: integerInRange(
        input.maxDurationHours,
        defaultMaxDurationMs,
        minMaxDurationMs,
        maxMaxDurationMs,
        3_600_000,
      ),
      startedAt: now,
      deadlineAt: now + integerInRange(
        input.maxDurationHours,
        defaultMaxDurationMs,
        minMaxDurationMs,
        maxMaxDurationMs,
        3_600_000,
      ),
      status: 'active',
      consecutiveErrors: 0,
      lastSnapshot: snapshot,
      lastSnapshotHash: snapshotHash(snapshot),
      lastReadinessHash: readinessHash(snapshot),
      lastNotifiedHash: hasActionableEvidence(snapshot) ? actionableHash(snapshot) : undefined,
      readySince: isReady(snapshot) ? now : undefined,
    }
    store.watches[key] = watch
    try {
      await acquireLease(watch)
      await persistStore()
    } catch (error) {
      releaseLease(key)
      if (existing) store.watches[key] = existing
      else delete store.watches[key]
      await persistStore().catch(() => undefined)
      throw error
    }
    schedulePoll(key, watch.pollIntervalMs)
    if (watch.fix && hasActionableEvidence(snapshot)) queueFixTurn(watch, snapshot)

    return [
      `Started Amp-native watch for ${repo}#${parsed.pr} in this thread. Keep-alive lease acquired.`,
      `Defaults/effective limits: poll ${watch.pollIntervalMs / 1_000}s, quiet ${watch.quietPeriodMs / 60_000}m, max active duration ${watch.maxDurationMs / 3_600_000}h.`,
      snapshotSummary(snapshot),
      isReady(snapshot)
        ? 'Readiness is green; the lease remains held through the quiet period.'
        : 'The lease remains held while required CI or review work is pending.',
      `Durable webhook credential (optional reactivation after success): ${webhookCredentialFile}. Treat its contents as a bearer secret and configure GitHub externally; this plugin never changes repository hooks.`,
      'Never merge or deploy.',
    ].join('\n')
  }

  async function selectWatches(
    input: Record<string, unknown>,
    thread: PluginThread,
  ): Promise<PersistedWatch[]> {
    const store = await loadStore()
    if (typeof input.pr !== 'string' || !input.pr.trim()) {
      return Object.values(store.watches).filter((watch) => watch.threadID === thread.id)
    }
    const parsed = parsePRInput(input.pr)
    const repo = normalizeRepo(
      typeof input.repo === 'string' && input.repo.trim()
        ? input.repo
        : parsed.repo ?? await currentRepo(),
    )
    const watch = store.watches[`${repo.toLowerCase()}#${parsed.pr}`]
    return watch ? [watch] : []
  }

  async function statusText(
    input: Record<string, unknown>,
    thread: PluginThread,
  ): Promise<string> {
    const watches = await selectWatches(input, thread)
    if (watches.length === 0) return 'No matching phx-watch-pr lifecycle was found.'
    return watches.map((watch) => [
      `${watch.repo}#${watch.pr}: ${watch.status}${watch.terminalReason ? ` — ${watch.terminalReason}` : ''}`,
      watch.lastSnapshot ? snapshotSummary(watch.lastSnapshot) : 'No snapshot yet.',
      watch.status === 'active'
        ? `Lease active; hard deadline ${new Date(watch.deadlineAt).toISOString()}.`
        : 'No keep-alive lease is held.',
      `Optional durable webhook credential file: ${webhookCredentialFile}.`,
    ].join('\n')).join('\n\n')
  }

  async function stopWatches(
    input: Record<string, unknown>,
    thread: PluginThread,
  ): Promise<string> {
    const watches = await selectWatches(input, thread)
    const active = watches.filter((watch) => watch.status === 'active')
    for (const watch of active) {
      await finishWatch(watch.key, 'stopped', 'Stopped explicitly by the worker thread.', false)
    }
    return active.length === 0
      ? 'No matching active watch was found.'
      : `Stopped ${active.length} watch lifecycle(s) and released every keep-alive lease.`
  }

  async function handleWebhook(
    event: WebhookEvent,
    ctx: WebhookHandlerContext,
  ): Promise<void> {
    if (ctx.signal.aborted) throw new Error('Webhook handler was cancelled.')
    const eventName = event.headers['x-github-event']
    if (!eventName || !acceptedWebhookEvents.has(eventName)) return
    let payload: any
    try {
      payload = JSON.parse(new TextDecoder().decode(event.body))
    } catch {
      return
    }
    const targets = webhookTargets(payload)
    if (!targets.repo || (targets.prs.length === 0 && targets.headShas.length === 0)) return
    const store = await loadStore()
    if (store.recentWebhookIDs.includes(event.id)) return
    const matching = Object.values(store.watches).filter((watch) =>
      watch.repo.toLowerCase() === targets.repo?.toLowerCase() &&
      (
        targets.prs.includes(watch.pr) ||
        Boolean(watch.lastSnapshot?.headSha &&
          targets.headShas.includes(watch.lastSnapshot.headSha))
      ) &&
      ['active', 'succeeded'].includes(watch.status),
    )
    if (matching.length === 0) return

    store.recentWebhookIDs.push(event.id)
    store.recentWebhookIDs = store.recentWebhookIDs.slice(-200)
    const now = Date.now()
    for (const watch of matching) {
      if (watch.status === 'succeeded') {
        watch.status = 'active'
        watch.terminalReason = undefined
        watch.terminalAt = undefined
        watch.startedAt = now
        watch.deadlineAt = now + watch.maxDurationMs
        watch.readySince = undefined
        watch.reactivationProbeUntil = now + webhookProbeMs
      }
      await acquireLease(watch)
      schedulePoll(watch.key, 0)
    }
    await persistStore()
  }

  void amp.createWebhook({
    key: 'phx-watch-pr',
    headers: ['x-github-event', 'x-github-delivery'],
    handler: handleWebhook,
  }).then((registration) => {
    mkdirSync(webhookDirectory, { recursive: true, mode: 0o700 })
    writeFileSync(webhookCredentialFile, `${registration.url}\n`, { mode: 0o600 })
  }).catch((error) => {
    amp.logger.log('phx-watch-pr durable webhook is unavailable', errorText(error))
  })

  amp.registerTool({
    name: 'elixir_phoenix_watch_pr',
    description:
      'Start, inspect, or stop the Amp-native phx-watch-pr lifecycle. It holds an Orb keep-alive lease while required non-deployment CI or unresolved review threads are pending, deduplicates unchanged polls, and never merges or deploys.',
    inputSchema: {
      type: 'object',
      properties: {
        action: { enum: ['start', 'status', 'stop'] },
        pr: { type: 'string', description: 'PR number or URL. Required for start.' },
        repo: { type: 'string', description: 'Optional OWNER/NAME when pr is a number.' },
        checksOnly: { type: 'boolean' },
        fix: { type: 'boolean' },
        pollIntervalSeconds: { type: 'number', minimum: 30, maximum: 300 },
        quietPeriodMinutes: { type: 'number', minimum: 5, maximum: 60 },
        maxDurationHours: { type: 'number', minimum: 0.5, maximum: 24 },
      },
      required: ['action'],
      additionalProperties: false,
    },
    async execute(input, ctx) {
      try {
        if (input.action === 'start') return await startWatch(input, ctx.thread)
        if (input.action === 'status') return await statusText(input, ctx.thread)
        if (input.action === 'stop') return await stopWatches(input, ctx.thread)
        return 'Unknown watch action.'
      } catch (error) {
        return `phx-watch-pr ${String(input.action)} failed: ${errorText(error)}`
      }
    },
  })

  amp.onDispose(() => {
    disposed = true
    for (const key of timers.keys()) clearTimer(key)
    for (const key of leases.keys()) releaseLease(key)
  })

  void (async () => {
    try {
      const store = await loadStore()
      for (const watch of Object.values(store.watches)) {
        if (watch.status !== 'active') continue
        if (Date.now() >= watch.deadlineAt) {
          await finishWatch(
            watch.key,
            'timed_out',
            'Persisted watch exceeded its hard deadline during plugin reload; state is incomplete.',
          )
          continue
        }
        watch.fixInFlightHash = undefined
        if (
          watch.fix &&
          watch.lastSnapshot &&
          hasActionableEvidence(watch.lastSnapshot) &&
          watch.lastFixHash !== fixHash(watch.lastSnapshot)
        ) {
          watch.pendingFixHash = fixHash(watch.lastSnapshot)
        }
        await persistStore()
        await acquireLease(watch)
        schedulePoll(watch.key, 0)
        if (watch.pendingFixHash && watch.lastSnapshot) {
          queueFixTurn(watch, watch.lastSnapshot)
        }
      }
    } catch (error) {
      amp.logger.log('phx-watch-pr recovery failed', errorText(error))
    }
  })()
}

import assert from 'node:assert/strict'
import {
  mkdirSync,
  mkdtempSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

const pluginPath = process.argv[2]
const workspace = process.argv[3]
if (!pluginPath || !workspace) {
  throw new Error('usage: amp_plugin_harness.ts <plugin> <workspace>')
}
const outsideWorkspace = mkdtempSync(join(tmpdir(), 'amp-elixir-phoenix-outside-'))
mkdirSync(join(workspace, 'lib', 'app'), { recursive: true })
symlinkSync(outsideWorkspace, join(workspace, 'lib', 'app', 'outside-link'), 'dir')
writeFileSync(join(outsideWorkspace, 'existing.ex'), 'defmodule Existing do\nend\n')
process.on('exit', () => rmSync(outsideWorkspace, { recursive: true, force: true }))
const { default: plugin } = await import(pathToFileURL(pluginPath).href)

const commands = new Map<string, Function>()
const tools = new Map<string, any>()
const handlers = new Map<string, Function>()
const agents: any[] = []
const notices: string[] = []
let config: Record<string, unknown> = {}
let configError = false
let childFailure = 'security-analyzer'
let threadCounter = 0

const uri = (path: string) => ({ toString: () => path, path })
const amp: any = {
  registerCommand(name: string, _metadata: unknown, handler: Function) {
    commands.set(name, handler)
  },
  registerTool(definition: any) {
    tools.set(definition.name, definition)
  },
  on(name: string, handler: Function) {
    handlers.set(name, handler)
  },
  createAgent(definition: any) {
    const agent = {
      definition,
      async run() {
        if (definition.name.includes(childFailure)) {
          throw new Error(`simulated ${definition.name} failure`)
        }
        return {
          threadID: `T-child-${definition.name}`,
          text: `finding from ${definition.name}`,
        }
      },
    }
    agents.push(agent)
    return agent
  },
  getBuiltinAgent() {
    return {
      async createThread() {
        const appended: unknown[] = []
        return {
          id: `T-created-${++threadCounter}`,
          appended,
          async appendUserMessage(message: unknown) {
            appended.push(message)
          },
        }
      },
    }
  },
  configuration: {
    async get() {
      if (configError) throw new Error('config unavailable')
      return config
    },
    async update(value: Record<string, unknown>) {
      config = { ...config, ...value }
    },
    async delete(key: string) {
      delete config[key]
    },
  },
  helpers: {
    shellCommandFromToolCall(call: any) {
      return call.tool === 'shell_command'
        ? { command: call.input.command }
        : null
    },
    filesModifiedByToolCall(call: any) {
      const modified = call.input?.modified
      return Array.isArray(modified) ? modified.map(uri) : null
    },
    toolCallsInMessages(messages: any[]) {
      return messages
    },
    filePathFromURI(value: any) {
      return typeof value === 'string' ? value : value.path
    },
  },
  system: { workspaceRoot: workspace },
  activeThread: { current: undefined },
  logger: { log() {} },
  ui: {
    async notify(message: string) {
      notices.push(message)
    },
  },
}
plugin(amp)

assert.equal(commands.size, 45)
assert.equal(tools.size, 2)
assert.equal(agents.length, 9)
assert.ok(
  agents.every(
    (agent) =>
      JSON.stringify(agent.definition.tools) ===
      JSON.stringify(['Read', 'finder']),
  ),
)

const toolCall = handlers.get('tool.call')!
const allowedEdit = resolve(workspace, 'lib/app/file.ex')
const siblingEdit = resolve(workspace, 'lib/application/file.ex')
assert.deepEqual(await toolCall({ tool: 'Read', input: {} }), {
  action: 'allow',
})
config = { elixirPhoenixEditLock: { mode: 'all', paths: [] } }
assert.equal(
  (
    await toolCall({
      tool: 'shell_command',
      input: { command: 'git status' },
    })
  ).action,
  'reject-and-continue',
)
assert.equal(
  (
    await toolCall({
      tool: 'edit_file',
      input: { modified: [allowedEdit] },
    })
  ).action,
  'reject-and-continue',
)
assert.deepEqual(await toolCall({ tool: 'Read', input: {} }), {
  action: 'allow',
})
config = { elixirPhoenixEditLock: { mode: 'paths', paths: ['lib/app'] } }
assert.deepEqual(
  await toolCall({
    tool: 'edit_file',
    input: { modified: [allowedEdit] },
  }),
  { action: 'allow' },
)
assert.equal(
  (
    await toolCall({
      tool: 'edit_file',
      input: { modified: [siblingEdit] },
    })
  ).action,
  'reject-and-continue',
)
const symlinkEdit = resolve(workspace, 'lib/app/outside-link/file.ex')
assert.equal(
  (
    await toolCall({
      tool: 'edit_file',
      input: { modified: [symlinkEdit] },
    })
  ).action,
  'reject-and-continue',
  'an allowed directory must not escape through a symlink',
)
const existingSymlinkEdit = resolve(
  workspace,
  'lib/app/outside-link/existing.ex',
)
assert.equal(
  (
    await toolCall({
      tool: 'edit_file',
      input: { modified: [existingSymlinkEdit] },
    })
  ).action,
  'reject-and-continue',
  'an existing target reached through a symlink must be blocked',
)
config = {
  elixirPhoenixEditLock: { mode: 'paths', paths: ['lib/app/outside-link'] },
}
assert.equal(
  (
    await toolCall({
      tool: 'edit_file',
      input: { modified: [symlinkEdit] },
    })
  ).action,
  'reject-and-continue',
  'an allowed prefix that is a symlink outside the workspace must fail closed',
)
config = {
  elixirPhoenixEditLock: { mode: 'paths', paths: ['../outside-workspace'] },
}
assert.deepEqual(await toolCall({ tool: 'Read', input: {} }), {
  action: 'allow',
})
assert.equal(
  (
    await toolCall({
      tool: 'edit_file',
      input: { modified: [allowedEdit] },
    })
  ).action,
  'reject-and-continue',
  'an escaping persisted allow-prefix must fail closed',
)
config = { elixirPhoenixEditLock: { mode: 'unexpected', paths: [] } }
assert.equal(
  (
    await toolCall({
      tool: 'edit_file',
      input: { modified: [allowedEdit] },
    })
  ).action,
  'reject-and-continue',
  'malformed persisted lock state must fail closed',
)
configError = true
assert.equal(
  (await toolCall({ tool: 'Read', input: {} })).action,
  'reject-and-continue',
)
configError = false

const parallel = tools.get('elixir_phoenix_parallel_review')
const parallelResult = await parallel.execute(
  { scope: 'review changes' },
  { thread: { id: 'T-parent' } },
)
assert.match(parallelResult, /finding from elixir-phoenix-elixir-reviewer/)
assert.match(parallelResult, /Security reviewer\nStatus: ERROR/)
assert.match(
  parallelResult,
  /simulated elixir-phoenix-security-analyzer failure/,
)

const notify = async (message: string) => {
  notices.push(message)
}
const context = (id: string) => ({
  thread: { id },
  ui: {
    async notify(message: string) {
      await notify(message)
    },
  },
})
const draftContext = { ui: { notify } }
const phxReview = commands.get('elixir-phoenix-phx-review')!
const clearPending = commands.get(
  'elixir-phoenix-clear-pending-workflow',
)!
const agentStart = handlers.get('agent.start')!

await phxReview(draftContext)
amp.activeThread.current = { id: 'T-active-draft' }
assert.deepEqual(
  await agentStart(
    { thread: { id: 'T-other-draft' } },
    context('T-other-draft'),
  ),
  {},
  'a non-active thread must not consume a draft workflow',
)
let startResult = await agentStart(
  { thread: { id: 'T-active-draft' } },
  context('T-active-draft'),
)
assert.match(startResult.message.content, /explicit-skill name="phx-review"/)
assert.deepEqual(
  await agentStart(
    { thread: { id: 'T-active-draft' } },
    context('T-active-draft'),
  ),
  {},
  'a workflow must be consumed after one turn',
)

await phxReview(draftContext)
await clearPending(draftContext)
assert.deepEqual(
  await agentStart(
    { thread: { id: 'T-active-draft' } },
    context('T-active-draft'),
  ),
  {},
  'clearing must prevent draft workflow injection',
)

const phxFull = commands.get('elixir-phoenix-phx-full')!
const agentEnd = handlers.get('agent.end')!
const nativeCommandIDs = new Set([
  'elixir-phoenix-clear-pending-workflow',
  'elixir-phoenix-specialist',
  'elixir-phoenix-parallel-review',
  'elixir-phoenix-parallel-investigate',
  'elixir-phoenix-edit-lock',
])
const workflowCommands = [...commands.entries()].filter(
  ([id]) => !nativeCommandIDs.has(id),
)
assert.equal(workflowCommands.length, 40)
for (const [id, handler] of workflowCommands) {
  const skillName = id.replace(/^elixir-phoenix-/, '')
  const threadID = `T-workflow-${skillName}`
  const workflowContext = context(threadID)
  await handler(workflowContext)
  const start = await agentStart({ thread: { id: threadID } }, workflowContext)
  assert.match(
    start.message.content,
    new RegExp(`<explicit-skill name="${skillName}">`),
    `${id} must inject its matching installed skill`,
  )
  assert.deepEqual(
    await agentStart({ thread: { id: threadID } }, workflowContext),
    {},
    `${id} must be consumed after one turn`,
  )
  if (skillName === 'phx-full') {
    await agentEnd(
      { thread: { id: threadID }, status: 'cancelled', messages: [] },
      workflowContext,
    )
  }
}

const armFull = async (id: string) => {
  const ctx = context(id)
  await phxFull(ctx)
  const result = await agentStart({ thread: { id } }, ctx)
  assert.match(result.message.content, /explicit-skill name="phx-full"/)
  return ctx
}
const edit = {
  call: {
    tool: 'edit_file',
    input: { modified: [resolve(workspace, 'lib/app.ex')] },
  },
  result: { status: 'done', output: {} },
}
const verify = (command: string, exitCode: unknown) => ({
  call: { tool: 'shell_command', input: { command } },
  result: {
    status: 'done',
    output: exitCode === undefined ? {} : { exitCode },
  },
})
const runningVerify = (command: string, pid: number) => ({
  call: { tool: 'shell_command', input: { command } },
  result: { status: 'done', output: { running: true, pid } },
})
const verificationStatus = (pid: number, exitCode: number) => ({
  call: { tool: 'shell_command_status', input: { pid } },
  result: { status: 'done', output: { running: false, exitCode } },
})
const runningVerificationStatus = (pid: number) => ({
  call: { tool: 'shell_command_status', input: { pid } },
  result: { status: 'done', output: { running: true } },
})

let ctx = await armFull('T-before-edit')
let result = await agentEnd(
  {
    thread: { id: 'T-before-edit' },
    status: 'done',
    messages: [verify('mix test', 0), edit],
  },
  ctx,
)
assert.equal(
  result.action,
  'continue',
  'verification before latest edit must not pass the gate',
)

ctx = await armFull('T-after-edit')
result = await agentEnd(
  {
    thread: { id: 'T-after-edit' },
    status: 'done',
    messages: [edit, verify('mix test', 0)],
  },
  ctx,
)
assert.equal(result, undefined, 'zero exit after edit should pass')

ctx = await armFull('T-format-check')
result = await agentEnd(
  {
    thread: { id: 'T-format-check' },
    status: 'done',
    messages: [edit, verify('mix format --check-formatted', 0)],
  },
  ctx,
)
assert.equal(result, undefined, 'format check after edit should pass')

ctx = await armFull('T-plain-format')
result = await agentEnd(
  {
    thread: { id: 'T-plain-format' },
    status: 'done',
    messages: [edit, verify('mix format', 0)],
  },
  ctx,
)
assert.equal(result.action, 'continue', 'plain mix format must not pass')

ctx = await armFull('T-piped-test')
result = await agentEnd(
  {
    thread: { id: 'T-piped-test' },
    status: 'done',
    messages: [edit, verify('mix test | tail -20', 0)],
  },
  ctx,
)
assert.equal(result.action, 'continue', 'a piped mix test must not pass')

ctx = await armFull('T-echo-test')
result = await agentEnd(
  {
    thread: { id: 'T-echo-test' },
    status: 'done',
    messages: [edit, verify('echo mix test', 0)],
  },
  ctx,
)
assert.equal(result.action, 'continue', 'an echoed command must not pass')

ctx = await armFull('T-no-exit')
result = await agentEnd(
  {
    thread: { id: 'T-no-exit' },
    status: 'done',
    messages: [edit, verify('mix test', undefined)],
  },
  ctx,
)
assert.equal(result.action, 'continue', 'missing exit code must not pass')
result = await agentEnd(
  {
    thread: { id: 'T-no-exit' },
    status: 'done',
    messages: [verify('mix test', undefined)],
  },
  ctx,
)
assert.equal(result, undefined, 'gate must use only one continuation')
assert.ok(notices.some((message) => message.includes('stopped incomplete')))

ctx = await armFull('T-background-success')
result = await agentEnd(
  {
    thread: { id: 'T-background-success' },
    status: 'done',
    messages: [
      edit,
      runningVerify('mix test', 4101),
      verificationStatus(4101, 0),
    ],
  },
  ctx,
)
assert.equal(result, undefined, 'a successful polled verification should pass')

ctx = await armFull('T-background-failure')
result = await agentEnd(
  {
    thread: { id: 'T-background-failure' },
    status: 'done',
    messages: [
      edit,
      runningVerify('mix test', 4102),
      verificationStatus(4102, 1),
    ],
  },
  ctx,
)
assert.equal(result.action, 'continue', 'a failed polled verification must not pass')

ctx = await armFull('T-background-unrelated-pid')
result = await agentEnd(
  {
    thread: { id: 'T-background-unrelated-pid' },
    status: 'done',
    messages: [
      edit,
      runningVerify('mix test', 4104),
      verificationStatus(9999, 0),
      runningVerificationStatus(4104),
    ],
  },
  ctx,
)
assert.equal(
  result.action,
  'continue',
  'a successful status for an unrelated PID must not pass',
)

ctx = await armFull('T-background-before-edit')
result = await agentEnd(
  {
    thread: { id: 'T-background-before-edit' },
    status: 'done',
    messages: [
      runningVerify('mix test', 4103),
      edit,
      verificationStatus(4103, 0),
    ],
  },
  ctx,
)
assert.equal(
  result.action,
  'continue',
  'an edit must invalidate an earlier pending verification',
)

ctx = await armFull('T-cancelled')
assert.equal(
  await agentEnd(
    { thread: { id: 'T-cancelled' }, status: 'cancelled', messages: [] },
    ctx,
  ),
  undefined,
)
assert.equal(
  await agentEnd(
    { thread: { id: 'T-cancelled' }, status: 'done', messages: [edit] },
    ctx,
  ),
  undefined,
  'a cancelled full workflow must clear lifecycle state',
)

ctx = await armFull('T-no-edit')
for (let turn = 0; turn < 8; turn += 1) {
  assert.equal(
    await agentEnd(
      { thread: { id: 'T-no-edit' }, status: 'done', messages: [] },
      ctx,
    ),
    undefined,
  )
}
assert.ok(notices.some((message) => message.includes('expired after 8 no-edit turns')))
assert.equal(
  await agentEnd(
    { thread: { id: 'T-no-edit' }, status: 'done', messages: [edit] },
    ctx,
  ),
  undefined,
  'the no-edit turn guard must clear lifecycle state',
)

console.log('Amp plugin behavior harness passed')

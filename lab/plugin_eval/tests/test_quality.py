"""Tests for the output-quality suite (lab/plugin_eval/quality/) and its summarizer."""

import json
import os
import re

import pytest
import yaml

from lab.plugin_eval import quality

# Other suites put an unnormalized `.../tests/../../..` on sys.path, so resolve
# the module path before comparing against it.
QUALITY_PY = os.path.realpath(quality.__file__)
QUALITY_DIR = os.path.join(os.path.dirname(QUALITY_PY), "quality")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(QUALITY_PY)))
PLUGIN_DIRS = ["plugins/elixir-phoenix", "plugins/ecto", "plugins/lv"]
GRADER_TYPES = {"regex", "tool_used", "tool_order", "file_exists", "llm", "baseline"}
CASES = sorted(
    name for name in os.listdir(QUALITY_DIR)
    if os.path.isfile(os.path.join(QUALITY_DIR, name, "prompt.md"))
)


def _frontmatter(path):
    text = open(path).read()
    _, head, body = text.split("---\n", 2)
    return yaml.safe_load(head) or {}, body.strip()


def _grader(case, name):
    config, body = _frontmatter(os.path.join(QUALITY_DIR, case, "graders", f"{name}.md"))
    return config, body


def _passes(case, name, text):
    """Evaluate a regex grader the way `claude plugin eval` does (JS regex, flags i/m)."""
    config, _ = _grader(case, name)
    flags = (re.I if "i" in config.get("flags", "") else 0) | (re.M if "m" in config.get("flags", "") else 0)
    found = re.search(config["pattern"], text, flags) is not None
    return not found if config.get("match") == "not_contains" else found


def test_suite_has_cases():
    assert len(CASES) >= 5


@pytest.mark.parametrize("case", CASES)
def test_case_is_well_formed(case):
    case_dir = os.path.join(QUALITY_DIR, case)
    with open(os.path.join(case_dir, "case.yaml")) as f:
        spec = yaml.safe_load(f)
    assert spec["schema_version"] == "1.1" and spec["name"] == case
    # phx needs its ecto/lv dependencies loaded alongside it, or CC disables it.
    resolved = [os.path.normpath(os.path.join(case_dir, p)) for p in spec["plugins"]]
    assert resolved == [os.path.join(PROJECT_ROOT, p) for p in PLUGIN_DIRS]
    scaffold = os.path.join(case_dir, spec["context"]["scaffold_script"])
    assert os.access(scaffold, os.X_OK)

    prompt, body = _frontmatter(os.path.join(case_dir, "prompt.md"))
    # Explicit invocation: the suite measures skill output, not routing.
    invoked = re.match(r"/(phx|ecto|lv):([\w-]+) ", body)
    assert invoked
    assert "quality" in prompt["tags"]
    # `/phx:oban ...` on a `user-invocable: false` skill ends the run after 0 turns
    # with an empty result, and the with-arm scores as if the plugin did nothing.
    plugin_dir = {"phx": "elixir-phoenix", "ecto": "ecto", "lv": "lv"}[invoked.group(1)]
    skill_md = os.path.join(PROJECT_ROOT, "plugins", plugin_dir, "skills", invoked.group(2), "SKILL.md")
    skill, _ = _frontmatter(skill_md)
    assert skill.get("user-invocable", True) is not False, f"{invoked.group(0).strip()} is not user-invocable"

    graders = os.listdir(os.path.join(case_dir, "graders"))
    assert graders
    for name in graders:
        config, grader_body = _frontmatter(os.path.join(case_dir, "graders", name))
        assert config["type"] in GRADER_TYPES, name
        if config["type"] == "llm":
            assert "PASS if" in grader_body and "FAIL if" in grader_body, name
        target = config.get("target")
        if isinstance(target, dict):
            # File targets take an exact path; a glob makes the grader throw.
            assert not re.search(r"[*?\[]", target["path"]), name
            # .claude/ is write-protected in eval runs; a grader there can never pass.
            assert not target["path"].startswith(".claude/"), name


GOOD_PRODUCT = """
  schema "products" do
    field :weight_kg, :float
    field :price, :decimal
  end
  def changeset(product, attrs) do
    product
    |> cast(attrs, [:name, :sku, :weight_kg, :stock,
                    :price])
"""
FLOAT_PRODUCT = GOOD_PRODUCT.replace("field :price, :decimal", "field :price, :float")


def test_money_graders_accept_decimal_or_cents_and_reject_float():
    assert _passes("money-field", "schema-money-type", GOOD_PRODUCT)
    assert _passes("money-field", "schema-money-type", "field :price_cents, :integer")
    assert _passes("money-field", "schema-no-float", GOOD_PRODUCT)
    assert _passes("money-field", "changeset-casts-price", GOOD_PRODUCT)
    assert not _passes("money-field", "schema-money-type", FLOAT_PRODUCT)
    assert not _passes("money-field", "schema-no-float", FLOAT_PRODUCT)
    assert _passes("money-field", "migration-money-type", "add :price, :decimal, precision: 10, scale: 2")
    assert not _passes("money-field", "migration-no-float", "add :price, :float")


def test_liveview_graders_reject_the_user_live_copy():
    naive = "def mount(_p, _s, socket) do\n  {:ok, assign(socket, products: Catalog.list_products())}\nend"
    good = (
        "def mount(_p, _s, socket) do\n"
        "  {:ok, socket |> stream(:products, []) |> assign(page: 1)}\nend\n"
        "if connected?(socket), do: Catalog.list_products(limit: 50)"
    )
    assert not _passes("liveview-products", "no-query-assigned-in-mount", naive)
    assert not _passes("liveview-products", "uses-stream", naive)
    assert _passes("liveview-products", "no-query-assigned-in-mount", good)
    assert _passes("liveview-products", "uses-stream", good)
    assert _passes("liveview-products", "async-or-connected", good)
    assert _passes("liveview-products", "paginates", good)


def test_oban_graders_want_string_keys_and_ids():
    worker = (
        'use Oban.Worker, queue: :mailers, unique: [period: 300, keys: [:user_id]]\n'
        'def perform(%Oban.Job{args: %{"user_id" => user_id}}) do\n'
        "  case Accounts.get_user(user_id) do\n    nil -> {:cancel, :user_not_found}\n"
    )
    assert _passes("oban-welcome", "worker-string-keys", worker)
    assert _passes("oban-welcome", "worker-no-atom-keys", worker)
    assert _passes("oban-welcome", "safe-to-retry", worker)
    assert _passes("oban-welcome", "handles-missing-user", worker)
    assert not _passes("oban-welcome", "worker-no-atom-keys", "def perform(%Oban.Job{args: %{user_id: id}})")
    assert _passes("oban-welcome", "enqueues-user-id", "%{user_id: user.id} |> WelcomeEmailWorker.new()")
    # Transactional enqueue from a no-plugin run; `%{user: user}` here is the Multi result, not job args.
    multi = "|> Oban.insert(:welcome_email, fn %{user: user} ->\n  WelcomeEmailWorker.new(%{user_id: user.id})\nend)"
    assert _passes("oban-welcome", "enqueues-user-id", multi)
    assert not _passes("oban-welcome", "enqueues-user-id", 'WelcomeEmailWorker.new(%{"user" => user})')


def test_subtle_review_graders_do_not_fire_on_the_obvious_findings():
    obvious = ("N+1: Repo.get!(User, ...) per order; use preload: :user. String.to_atom on params. "
               "Use :decimal for total. Anyone can cancel any order.")
    for grader in ("finds-external-resource", "finds-unsupervised-task", "finds-lost-locale"):
        assert not _passes("review-orders", grader, obvious), grader
    assert _passes("review-orders", "finds-external-resource", "add @external_resource so edits recompile")


def test_plan_checkbox_grader_needs_a_task_line():
    assert _passes("plan-favorites", "plan-checkboxes", "## Phase 1\n\n- [ ] Migration: favorites\n")
    assert not _passes("plan-favorites", "plan-checkboxes", "1. Migration: favorites\n- [x] done\n")


def _trace(path, *, plugins=("phx", "ecto", "lv"), plugin_errors=None, denied_path=None):
    events = [{"type": "system", "subtype": "init", "plugins": [{"name": p} for p in plugins],
               "plugin_errors": plugin_errors or []}]
    if denied_path:
        events.append({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "Write", "input": {"file_path": denied_path}}]}})
        events.append({"type": "system", "subtype": "permission_denied", "tool_name": "Write", "tool_use_id": "t1"})
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")


def _run(trace, graders, *, error=None):
    return {"tracePath": str(trace), "error": error, "costUsd": 0.4, "judgeCostUsd": 0.1,
            "graders": [{"name": n, "passed": p, "scored": s} for n, p, s in graders]}


def test_summary_reports_per_grader_discrimination_and_denials(tmp_path):
    with_trace, without_trace = tmp_path / "w.jsonl", tmp_path / "wo.jsonl"
    _trace(with_trace, denied_path="/tmp/e-x/home/cwd/.claude/plans/review/reviews/elixir.md")
    _trace(without_trace, plugins=())
    data = {"cases": [{
        "name": "review-orders",
        "aggregates": {"score": 0.75, "scoreWithout": 0.5, "delta": 0.25},
        "arms": {
            "with": [_run(with_trace, [("n1", True, True), ("authz", True, True), ("edits", True, True),
                                       ("skill", False, False)])],
            "without": [_run(without_trace, [("n1", True, True), ("authz", False, True), ("edits", True, True),
                                             ("skill", False, False)], error="timed out after 900s")],
        },
    }]}

    summary = quality.summarize(data, str(tmp_path))

    row = summary["cases"][0]
    assert row["cost"] == 1.0
    assert {name: g["verdict"] for name, g in row["graders"].items()} == {
        "n1": "both pass", "authz": "plugin +", "edits": "both pass", "skill": "indicator"}
    assert summary["denied"] == [("review-orders", "with", "Write /tmp/e-x/home/cwd/.claude/plans/review/reviews/elixir.md")]
    assert summary["run_errors"] == [("review-orders", "without", "timed out after 900s")]
    # A no-plugin arm without phx is expected; only the with-arm is checked for load errors.
    assert summary["load_errors"] == []


def test_with_arm_without_phx_is_a_load_error(tmp_path):
    trace = tmp_path / "w.jsonl"
    _trace(trace, plugins=("ecto", "lv"), plugin_errors=[{"type": "dependency-unsatisfied"}])
    data = {"cases": [{"name": "c", "aggregates": {}, "arms": {"with": [_run(trace, [])], "without": []}}]}

    assert quality.summarize(data, str(tmp_path))["load_errors"] == [("c", [{"type": "dependency-unsatisfied"}])]


def test_archive_keeps_both_arms(tmp_path):
    with_trace, without_trace = tmp_path / "w.jsonl", tmp_path / "wo.jsonl"
    _trace(with_trace)
    _trace(without_trace, plugins=())
    results = tmp_path / "results"
    results.mkdir()
    data = {"cases": [{"name": "c", "arms": {"with": [_run(with_trace, [])], "without": [_run(without_trace, [])]}}]}

    assert quality.archive_traces(str(results), data) == 2
    with_trace.unlink()
    without_trace.unlink()

    assert quality.summarize(data, str(results))["unreadable"] == 0


@pytest.mark.parametrize("with_rate,without_rate,expected", [
    (1.0, 0.0, "plugin +"), (0.0, 1.0, "plugin -"), (1.0, 1.0, "both pass"),
    (0.0, 0.0, "both fail"), (0.5, 0.5, "tie"), (1.0, None, "with-only"),
])
def test_verdict(with_rate, without_rate, expected):
    assert quality.verdict(with_rate, without_rate) == expected

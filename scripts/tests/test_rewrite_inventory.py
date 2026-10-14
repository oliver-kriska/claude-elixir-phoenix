from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "plugins/rewrite/skills/analyze/scripts/inventory.py"
)


def load_inventory():
    spec = importlib.util.spec_from_file_location("rewrite_inventory", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


inv = load_inventory()


def write(root: Path, files: dict[str, str]) -> Path:
    for relpath, content in files.items():
        path = root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


@pytest.fixture
def rails_app(tmp_path: Path) -> Path:
    return write(
        tmp_path / "rails",
        {
            "Gemfile": 'gem "rails"\ngem "redis"\ngem "resque"\ngem "turbo-rails"\n',
            "Gemfile.lock": "GEM\n  specs:\n    rails (8.0.0)\n    sinatra (4.0.0)\n"
            "    redis (5.0.0)\n    resque (2.6.0)\n    turbo-rails (2.0.0)\n",
            "config/routes.rb": "Rails.application.routes.draw do\nend\n",
            "app/models/message.rb": "class Message < ApplicationRecord\n"
            "  after_create_commit :broadcast_create\n"
            "  # Debounce because SQLite locks on concurrent writes\n"
            "end\n",
            "app/jobs/push_job.rb": "class PushJob < ApplicationJob\n  def perform; end\nend\n",
            "app/javascript/service_worker.js": "self.addEventListener('push', () => {})\n",
            "app/channels/room_channel.rb": "class RoomChannel < ApplicationCable::Channel\nend\n",
            "test/models/message_test.rb": "class MessageTest\n"
            "  # after_create_commit because we need it\nend\n",
            "AGENTS.md": "# Agent rules\n",
        },
    )


@pytest.fixture
def express_app(tmp_path: Path) -> Path:
    return write(
        tmp_path / "express",
        {
            "package.json": json.dumps(
                {
                    "dependencies": {"express": "^4", "jsonwebtoken": "^9"},
                    "devDependencies": {"jest": "^29"},
                }
            ),
            "src/routes/api/users.ts": "router.get('/user', auth, handler)\n",
            "src/routes/api/__tests__/users.test.ts": "it('works', () => {})\n",
            "src/app.ts": "const app = express()\n",
        },
    )


def stacks(result: dict) -> set[str]:
    return {s["stack"] for s in result["stacks"]}


def signals(result: dict) -> dict[str, str]:
    return {s["signal"]: s["via"] for s in result["infra_signals"]}


def test_detects_rails_stack_from_direct_deps_only(rails_app: Path) -> None:
    result = inv.inventory(str(rails_app), None, 50)

    assert "rails" in stacks(result)
    # sinatra appears only in Gemfile.lock (transitive) and must not become a stack
    assert not any("sinatra" in s for s in stacks(result))


def test_infra_signals_mark_direct_dependencies(rails_app: Path) -> None:
    found = signals(inv.inventory(str(rails_app), None, 50))

    assert found.get("redis") == "direct"
    assert found.get("resque") == "direct"


def test_entry_points_classify_rails_layout(rails_app: Path) -> None:
    entries = inv.inventory(str(rails_app), None, 50)["entry_points"]

    assert "app/jobs/push_job.rb" in entries["jobs"]
    assert "config/routes.rb" in entries["routes"]
    assert "app/channels/room_channel.rb" in entries["realtime"]
    assert "test/models/message_test.rb" in entries["tests"]
    # a service worker is frontend code, not a background job
    assert "app/javascript/service_worker.js" not in entries.get("jobs", [])


def test_mechanism_hints_and_why_comments_skip_tests(rails_app: Path) -> None:
    result = inv.inventory(str(rails_app), None, 50)
    hinted = {
        f for hint in result["mechanism_hints"].values() for f in hint["top_files"]
    }
    why_files = {w.split(":", 1)[0] for w in result["why_comments"]}

    assert "app/models/message.rb" in hinted
    assert "test/models/message_test.rb" not in hinted
    assert "app/models/message.rb" in why_files
    assert "test/models/message_test.rb" not in why_files


def test_steering_files_listed_once_for_source_and_target(
    rails_app: Path, tmp_path: Path
) -> None:
    target = write(
        tmp_path / "target",
        {
            "AGENTS.md": "# Port rules\n",
            ".agents/skills/port/SKILL.md": "---\nname: port\n---\nTranslate literally.\n",
        },
    )

    steering = inv.inventory(str(rails_app), str(target), 50)["steering"]
    target_paths = [s["path"] for s in steering["target"]]

    assert [s["path"] for s in steering["source"]] == ["AGENTS.md"]
    assert sorted(target_paths) == [".agents/skills/port/SKILL.md", "AGENTS.md"]
    assert len(target_paths) == len(set(target_paths))


def test_express_routes_match_by_basename_not_directory(express_app: Path) -> None:
    result = inv.inventory(str(express_app), None, 50)
    entries = result["entry_points"]

    assert "express/koa/hapi" in stacks(result)
    assert signals(result).get("auth") == "direct"
    assert "src/routes/api/__tests__/users.test.ts" in entries["tests"]
    assert "src/app.ts" not in entries.get("routes", [])


@pytest.mark.parametrize(
    ("relpath", "pattern", "expected"),
    [
        ("src/routes/api/users.ts", "*routes*.ts", False),
        ("config/routes.rb", "routes.rb", True),
        ("app/workers/mail_worker.rb", "*/workers/*", True),
        ("app/workers/nested/deep.rb", "*/workers/*", True),
        ("src/a/__tests__/x.ts", "*/__tests__/*", True),
    ],
)
def test_matches_basename_for_slashless_patterns(
    relpath: str, pattern: str, expected: bool
) -> None:
    assert inv.matches(relpath, pattern) is expected


def test_git_signals_report_hotspots_and_fix_commits(tmp_path: Path) -> None:
    repo = write(tmp_path / "repo", {"app.rb": "a\n", "Gemfile": 'gem "rails"\n'})
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run([*git, "commit", "-qm", "init"], check=True)
    (repo / "app.rb").write_text("b\n", encoding="utf-8")
    subprocess.run([*git, "commit", "-qam", "fix race in app"], check=True)

    short = inv.inventory(str(repo), None, 50)
    assert short["source"]["git"]["hotspots_suppressed"] is True
    assert short["source"]["git"]["hotspots"] == []
    assert "history too shallow (2 commits); hotspots suppressed" in inv.to_markdown(short)
    assert any("hotspots suppressed" in reason for reason in short["coverage"]["limitations"])

    for n in range(18):
        (repo / "app.rb").write_text(f"revision {n}\n", encoding="utf-8")
        subprocess.run([*git, "commit", "-qam", f"update {n}"], check=True)

    git_info = inv.inventory(str(repo), None, 50)["source"]["git"]
    hotspots = {h["file"]: h for h in git_info["hotspots"]}

    assert git_info["commit_count"] == 20
    assert git_info["hotspots_suppressed"] is False
    assert hotspots["app.rb"]["changes"] == 20
    assert hotspots["app.rb"]["fix_commits"] == 1

    limited = inv.inventory(str(repo), None, 19)
    assert limited["coverage"]["git_commits_scanned"] == 19
    assert limited["source"]["git"]["hotspots_suppressed"] is True

    shallow = tmp_path / "shallow"
    subprocess.run(["git", "clone", "-q", "--depth=20", repo.as_uri(), str(shallow)], check=True)
    cloned = inv.inventory(str(shallow), None, 50)
    assert cloned["coverage"]["git_commits_scanned"] == 20
    assert cloned["source"]["git"]["hotspots_suppressed"] is True
    assert cloned["source"]["git"]["hotspots"] == []


def test_cli_refuses_to_write_inside_source(rails_app: Path, capsys) -> None:
    code = inv.main([str(rails_app), "--json", str(rails_app / "inv.json")])

    assert code == 2
    assert not (rails_app / "inv.json").exists()
    assert "read-only" in capsys.readouterr().err


def test_cli_writes_json_and_markdown(rails_app: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"

    code = inv.main(
        [str(rails_app), "--json", str(out / "i.json"), "--md", str(out / "i.md")]
    )

    assert code == 0
    data = json.loads((out / "i.json").read_text(encoding="utf-8"))
    assert data["version"] == 3
    assert "rails" in (out / "i.md").read_text(encoding="utf-8")


def test_monorepo_detects_nested_app_roots(tmp_path: Path) -> None:
    repo = write(
        tmp_path / "mono",
        {
            "README.md": "# mono\n",
            "api/go.mod": "module example.com/api\n\ngo 1.22\n\nrequire github.com/redis/go-redis/v9 v9.5.0\n",
            "api/internal/workers/mailer.go": "package workers\n",
            "web/package.json": json.dumps({"dependencies": {"next": "14", "socket.io": "4"}}),
            "web/src/routes/index.ts": "export default {}\n",
            "web/test/fixtures/package.json": json.dumps({"dependencies": {"express": "4", "bullmq": "5", "electron": "30"}}),
            "web/test/fixtures/app/jobs/demo.js": "queue.add('demo')\n",
            "tools/Cargo.toml": "[package]\nname = 'x'\n\n[dependencies]\nclap = { version = \"4\" }\n",
            "ios/Package.swift": "// swift-tools-version:5.9\n",
        },
    )

    result = inv.inventory(str(repo), None, 50)
    roots = {r["path"]: r for r in result["app_roots"]}

    assert {"api", "web", "web/test/fixtures"} <= set(roots)
    assert roots["web/test/fixtures"]["fixture"] is True
    assert {"go", "nextjs/remix/nuxt"} <= stacks(result)
    # stacks found only in test fixtures do not describe the application
    assert "express/koa/hapi" not in stacks(result)
    assert {"redis", "socket.io/ws"} <= set(signals(result))
    assert "bull/bullmq/agenda" not in signals(result)
    assert "desktop" not in result["shape_hints"]
    assert "api/internal/workers/mailer.go" in result["entry_points"]["jobs"]
    assert roots["tools"]["languages"] == ["rust"]
    assert roots["tools"]["stacks"] == ["rust (no framework pack matched)"]
    assert "cli" in result["shape_hints"]
    assert result["coverage"]["unparsed_manifests"] == ["ios/Package.swift"]


def test_coverage_reports_discovered_versus_returned(tmp_path: Path) -> None:
    files = {f"app/models/m{i:03}.rb": f"# cache because slow query {i}\n" for i in range(70)}
    repo = write(tmp_path / "big", {"Gemfile": 'gem "rails"\n', **files})

    result = inv.inventory(str(repo), None, 50)
    why = result["coverage"]["why_comments"]

    assert why == {"discovered": 70, "returned": 60, "sampling": "round-robin by file"}
    assert result["coverage"]["entry_points"]["models"] == {"discovered": 70, "returned": 70}
    assert result["mechanism_hints"]["caching"]["files"] == 70
    assert len(result["mechanism_hints"]["caching"]["top_files"]) == 8


def test_compare_flags_changed_snapshot(rails_app: Path, tmp_path: Path, capsys) -> None:
    prev = tmp_path / "prev.json"
    assert inv.main([str(rails_app), "--json", str(prev)]) == 0
    capsys.readouterr()

    assert inv.main([str(rails_app), "--compare", str(prev)]) == 0
    assert capsys.readouterr().out.strip() == "unchanged"

    (rails_app / "app/models/message.rb").write_text("class Message; end\n", encoding="utf-8")

    assert inv.main([str(rails_app), "--compare", str(prev)]) == 1
    assert "tree_fingerprint" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("files", "stack"),
    [
        ({"Cargo.toml": "[dependencies]\naxum = \"0.7\"\ntokio = { version = \"1\" }\n"},
         "rust-web (axum/actix/rocket)"),
        ({"build.sbt": 'libraryDependencies += "org.apache.pekko" %% "pekko-actor-typed" % "1.1.0"\n'},
         "scala (play/akka/pekko)"),
        ({"cpanfile": "requires 'Mojolicious';\n"}, "perl (mojolicious/catalyst/dancer)"),
        ({"wp-config.php": "<?php\n", "composer.json": "{}"}, "wordpress"),
        ({"requirements.txt": "requests==2.32\n", "etl.py": "import requests\n"},
         "python (no framework pack matched)"),
    ],
)
def test_detects_stacks_beyond_the_big_web_frameworks(
    tmp_path: Path, files: dict[str, str], stack: str
) -> None:
    repo = write(tmp_path / "app", files)

    assert stack in stacks(inv.inventory(str(repo), None, 50))


def test_shape_hints_flag_pipelines_and_consumers(tmp_path: Path) -> None:
    repo = write(
        tmp_path / "pipe",
        {
            "pyproject.toml": '[project]\ndependencies = [\n  "apache-airflow>=2.9",\n  "confluent-kafka>=2.4",\n]\n',
            "dags/nightly.py": "from airflow import DAG\n",
        },
    )

    hints = inv.inventory(str(repo), None, 50)["shape_hints"]

    assert "data-pipeline" in hints
    assert "worker/consumer" in hints


def test_every_stack_maps_to_an_existing_pack() -> None:
    kb = SCRIPT.parents[2] / "elixir-way/references"

    packs = {inv.stack_pack(s) for s in inv.STACK_MARKERS} | {inv.stack_pack("cobol (no framework pack matched)")}

    assert inv.stack_pack("nestjs") == "stacks/node.md"
    assert inv.stack_pack("perl (mojolicious/catalyst/dancer)") == "stacks/generic.md"
    assert [p for p in packs if not (kb / p).is_file()] == []


def test_stacks_carry_their_pack(express_app: Path) -> None:
    result = inv.inventory(str(express_app), None, 50)

    assert {s["stack"]: s["pack"] for s in result["stacks"]}["express/koa/hapi"] == "stacks/node.md"
    assert "- stack packs to read: `stacks/node.md`" in inv.to_markdown(result)


@pytest.mark.parametrize(
    ("requires", "http"),
    [
        ("github.com/segmentio/kafka-go v0.4.47", False),
        ("github.com/segmentio/kafka-go v0.4.47\n\tgithub.com/go-chi/chi/v5 v5.1.0", True),
        ("github.com/google/uuid v1.6.0", True),
    ],
)
def test_go_handlers_hint_http_only_without_a_pure_consumer(tmp_path: Path, requires: str, http: bool) -> None:
    repo = write(
        tmp_path / "svc",
        {
            "go.mod": f"module example.com/svc\n\ngo 1.23\n\nrequire (\n\t{requires}\n)\n",
            "internal/events/handler.go": "package events\n",
        },
    )

    hints = inv.inventory(str(repo), None, 50)["shape_hints"]

    assert ("http-api" in hints) is http


def test_node_password_dependencies_and_crypto_hints(tmp_path: Path) -> None:
    deps = ["bcryptjs", "express-jwt", "argon2", "@node-rs/bcrypt", "@node-rs/argon2"]
    repo = write(tmp_path / "auth", {
        "package.json": json.dumps({"dependencies": {d: "1" for d in [*deps, "@node-rs/crc32"]}}),
        "auth.ts": "bcrypt.hash(password); bcrypt.compare(password, digest);\n"
                   "argon2.hash(password); argon2.verify(digest, password);\n"
                   "bcrypt.hashSync(password); bcrypt.compareSync(password, digest);\n",
    })
    result = inv.inventory(str(repo), None, 50)
    auth = next(s for s in result["infra_signals"] if s["signal"] == "auth")
    assert auth["deps"] == sorted(deps)
    assert result["mechanism_hints"]["crypto-contracts"]["count"] == 6


def test_config_files_are_not_test_entry_points(tmp_path: Path) -> None:
    paths = ["tsconfig.spec.json", "e2e/.eslintrc.json", "test/.eslintrc.js",
             "tests/tsconfig.base", "playwright.config.ts", "spec/vitest.config.js", "tests/data.json"]
    repo = write(tmp_path / "app", {p: "{}\n" for p in paths})
    write(repo, {"e2e/login.spec.ts": "it('login', () => {})\n", "tests/test_api.py": "def test_api(): pass\n"})
    result = inv.inventory(str(repo), None, 50)
    assert result["entry_points"]["tests"] == ["e2e/login.spec.ts", "tests/test_api.py"]
    assert result["coverage"]["entry_points"]["tests"] == {"discovered": 2, "returned": 2}


def test_large_file_same_size_edit_changes_identity(tmp_path: Path) -> None:
    repo = write(tmp_path / "app", {"large.sql": "a" * (4 * 1024 * 1024 + 1)})
    before = inv.inventory(str(repo), None, 50)
    with (repo / "large.sql").open("r+b") as fh:
        fh.seek(4 * 1024 * 1024)
        fh.write(b"b")
    after = inv.inventory(str(repo), None, 50)
    assert before["source"]["tree_fingerprint"] != after["source"]["tree_fingerprint"]
    assert inv.compare(before, after)


def test_changed_source_during_scan_is_rejected(tmp_path: Path, monkeypatch, capsys) -> None:
    repo = write(tmp_path / "app", {"app.py": "before = 1\n"})
    original = inv.git_signals

    def mutate(root, max_commits):
        (repo / "app.py").write_text("after = 2\n")
        return original(root, max_commits)

    monkeypatch.setattr(inv, "git_signals", mutate)
    out = tmp_path / "inventory.json"
    assert inv.main([str(repo), "--json", str(out)]) == 2
    assert "changed during inventory" in capsys.readouterr().err
    assert not out.exists()


def test_symlinks_are_reported_without_reading_targets(tmp_path: Path) -> None:
    repo = write(tmp_path / "app", {"main.py": "pass\n"})
    outside = write(tmp_path / "outside", {"secret.py": "post_save.send()\n", "AGENTS.md": "Do not disclose\n"})
    (repo / "linked-service").symlink_to(outside, target_is_directory=True)
    (repo / "AGENTS.md").symlink_to(repo / "missing.md")
    (repo / "CLAUDE.md").symlink_to(outside / "AGENTS.md")
    result = inv.inventory(str(repo), None, 50)
    assert {link["path"] for link in result["coverage"]["skipped_symlinks"]} == {
        "AGENTS.md", "CLAUDE.md", "linked-service",
    }
    assert result["mechanism_hints"] == {}
    assert all(s["first_line"] == "" for s in result["steering"]["source"])
    assert "Do not disclose" not in json.dumps(result)


def test_manifest_truncation_is_explicit(tmp_path: Path) -> None:
    repo = write(tmp_path / "app", {"package.json": json.dumps({
        "dependencies": {f"dep-{n:03}": "1" for n in range(401)},
    })})
    result = inv.inventory(str(repo), None, 50)
    assert len(result["manifests"]["package.json"]) == 400
    assert result["coverage"]["manifests"]["package.json"] == {"discovered": 401, "returned": 400}


def test_monorepo_shapes_use_each_services_own_signals(tmp_path: Path) -> None:
    repo = write(tmp_path / "mono", {
        "api/go.mod": "module example.com/api\n",
        "api/handler.go": "package api\n",
        "consumer/go.mod": "module example.com/consumer\nrequire github.com/segmentio/kafka-go v0.4.47\n",
        "consumer/handler.go": "package consumer\n",
    })
    result = inv.inventory(str(repo), None, 50)
    roots = {r["path"]: r for r in result["app_roots"]}
    assert roots["api"]["shape_hints"] == ["http-api"]
    assert roots["consumer"]["shape_hints"] == ["worker/consumer"]
    assert set(result["shape_hints"]) == {"http-api", "worker/consumer"}


def test_extra_steering_roots_are_scanned_without_rescanning_source(tmp_path: Path) -> None:
    repo = tmp_path / "port"
    source = repo / "reference"
    (source / "app").mkdir(parents=True)
    (source / "app/main.py").write_text("print('hi')\n", encoding="utf-8")
    (source / "AGENTS.md").write_text("# Legacy notes\n", encoding="utf-8")
    (repo / "AGENTS.md").write_text("# Port rules: keep Rails names\n", encoding="utf-8")

    result = inv.inventory(str(source), None, 50, [str(repo)])

    assert [s["path"] for s in result["steering"]["source"]] == ["AGENTS.md"]
    assert [(s["root"], s["path"]) for s in result["steering"]["extra"]] == [(str(repo), "AGENTS.md")]
    md = inv.to_markdown(result)
    assert f"[extra] `{repo / 'AGENTS.md'}`" in md


def git_cmd(repo: Path, *args: str, **kwargs) -> subprocess.CompletedProcess:
    # A commit can start detached auto-maintenance, which writes into .git
    # while a test is snapshotting it.
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
         "-c", "maintenance.auto=false", "-c", "gc.auto=0", *args],
        check=True, capture_output=True, text=True, **kwargs,
    )


def git_repo(root: Path, files: dict[str, str]) -> Path:
    write(root, files)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    git_cmd(root, "add", ".")
    git_cmd(root, "commit", "-qm", "init")
    return root


def arm_fsmonitor(tmp_path: Path, probe: str) -> tuple[Path, list[str]]:
    repo = git_repo(tmp_path / "app", {"app.py": "a = 1\n"})
    git_cmd(repo, "config", "core.fsmonitor", probe)
    return repo, ["status"]


def arm_clean_filter(driver: str):
    def arm(tmp_path: Path, probe: str) -> tuple[Path, list[str]]:
        repo = git_repo(tmp_path / "app", {"app.py": "a = 1\n", ".gitattributes": f"*.py filter={driver}\n"})
        git_cmd(repo, "config", f"filter.{driver}.clean", f"{probe} --filter")
        git_cmd(repo, "config", f"filter.{driver}.required", "true")
        # Same size, new mtime: status re-hashes the file through the clean filter.
        os.utime(repo / "app.py", ns=(0, 0))
        return repo, ["status"]
    return arm


def arm_submodule_filter(tmp_path: Path, probe: str) -> tuple[Path, list[str]]:
    lib = git_repo(tmp_path / "lib", {"lib.py": "a = 1\n", ".gitattributes": "*.py filter=probe\n"})
    repo = git_repo(tmp_path / "app", {"app.py": "a = 1\n"})
    git_cmd(repo, "-c", "protocol.file.allow=always", "submodule", "--quiet", "add", str(lib), "vendored")
    git_cmd(repo, "commit", "-qm", "vendor")
    git_cmd(repo / "vendored", "config", "filter.probe.clean", f"{probe} --filter")
    os.utime(repo / "vendored/lib.py", ns=(0, 0))
    return repo, ["status"]


def arm_signature_check(tmp_path: Path, probe: str) -> tuple[Path, list[str]]:
    repo = git_repo(tmp_path / "app", {"app.py": "a = 1\n"})
    tree = git_cmd(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
    parent = git_cmd(repo, "rev-parse", "HEAD").stdout.strip()
    signed = (f"tree {tree}\nparent {parent}\nauthor t <t@t> 1700000000 +0000\n"
              "committer t <t@t> 1700000000 +0000\ngpgsig -----BEGIN PGP SIGNATURE-----\n \n iQEz\n"
              " -----END PGP SIGNATURE-----\n\nsigned\n")
    sha = git_cmd(repo, "hash-object", "-t", "commit", "-w", "--stdin", input=signed).stdout.strip()
    git_cmd(repo, "update-ref", "HEAD", sha)
    git_cmd(repo, "config", "log.showSignature", "true")
    git_cmd(repo, "config", "gpg.program", probe)
    return repo, ["log", "-1"]


@pytest.mark.parametrize(
    "arm",
    [arm_fsmonitor, arm_clean_filter("probe"), arm_clean_filter("probe=x"), arm_submodule_filter,
     arm_signature_check],
    ids=["fsmonitor", "clean-filter", "clean-filter-name-with-equals", "submodule-clean-filter",
         "signature-check"],
)
def test_git_never_runs_programs_configured_in_source(tmp_path: Path, arm) -> None:
    sentinel = tmp_path / "probe-ran"
    probe = tmp_path / "probe.sh"
    probe.write_text(f"#!/bin/sh\ntouch '{sentinel}'\n[ \"$1\" = --filter ] && exec cat\nexit 1\n",
                     encoding="utf-8")
    probe.chmod(0o755)
    repo, trigger = arm(tmp_path, str(probe))

    result = inv.inventory(str(repo), None, 50)

    assert result["source"]["git"]["available"] is True
    assert not sentinel.exists()
    # The probe is armed: plain git runs it, so the assertion above is not vacuous.
    subprocess.run(["git", "-C", str(repo), *trigger], capture_output=True, stdin=subprocess.DEVNULL)
    assert sentinel.exists()


def test_inherited_git_environment_does_not_redirect_source(tmp_path: Path, monkeypatch) -> None:
    source = git_repo(tmp_path / "source", {"app.py": "a = 1\n"})
    other = git_repo(tmp_path / "other", {"other.py": "b = 2\n"})
    git_cmd(other, "commit", "-q", "--allow-empty", "-m", "second")
    (other / "untracked.py").write_text("c = 3\n", encoding="utf-8")
    own_sha = git_cmd(source, "rev-parse", "HEAD").stdout.strip()
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))
    monkeypatch.setenv("GIT_INDEX_FILE", str(other / ".git/index"))

    git_info = inv.inventory(str(source), None, 50)["source"]["git"]

    assert git_info["sha"] == own_sha
    assert git_info["commit_count"] == 1
    assert git_info["dirty"] is False


def test_write_after_a_files_read_is_rejected(tmp_path: Path, monkeypatch, capsys) -> None:
    repo = write(tmp_path / "app", {"app.py": "before = 1\n", "lib.py": "pass\n"})
    original, wrote = inv.read_snapshot, []

    def read_then_write(path, *args, **kwargs):
        result = original(path, *args, **kwargs)
        if path.endswith("app.py") and not wrote:
            wrote.append(path)
            (repo / "app.py").write_text("after = 2\n", encoding="utf-8")
        return result

    monkeypatch.setattr(inv, "read_snapshot", read_then_write)
    out = tmp_path / "inventory.json"

    assert inv.main([str(repo), "--json", str(out)]) == 2
    assert wrote
    assert "changed during inventory" in capsys.readouterr().err
    assert not out.exists()


def test_file_swapped_between_stat_and_open_is_rejected(tmp_path: Path, monkeypatch) -> None:
    repo = write(tmp_path / "app", {"app.py": "before = 1\n"})
    aside = tmp_path / "app.py.orig"
    real_open, swapped = os.open, []

    def swap_open_restore(path, flags, *args, **kwargs):
        if str(path).endswith(os.sep + "app.py") and not swapped:
            swapped.append(path)
            os.rename(path, aside)
            Path(path).write_text("other = 2\n", encoding="utf-8")
            fd = real_open(path, flags, *args, **kwargs)
            os.replace(aside, path)
            return fd
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(inv.os, "open", swap_open_restore)

    with pytest.raises(ValueError, match="changed during inventory"):
        inv.inventory(str(repo), None, 50)
    assert swapped


@pytest.mark.parametrize(
    ("manifest", "text"),
    [
        ("pyproject.toml", '[project]\nname = "shop"\ndependencies = ["django>=5", "celery>=5", "redis>=5"]\n'),
        ("pyproject.toml", '[project]\nname = "shop"\ndependencies = [\n  "Django>=5",\n'
                           '  "celery[redis]>=5",\n  "redis>=5; python_version >= \'3.11\'",\n]\n'),
        ("pyproject.toml", '[tool.poetry]\nname = "shop"\n\n[tool.poetry.dependencies]\npython = "^3.11"\n'
                           'django = "^5.0"\ncelery = { version = "^5", extras = ["redis"] }\nredis = "^5"\n'),
        ("Pipfile", '[packages]\ndjango = "*"\ncelery = {extras = ["redis"], version = "*"}\n\n'
                    '[dev-packages]\nredis = "*"\n'),
    ],
    ids=["pep621-inline", "pep621-multiline", "poetry", "pipfile"],
)
def test_python_manifests_drive_stack_and_signals(tmp_path: Path, manifest: str, text: str) -> None:
    repo = write(tmp_path / "shop", {manifest: text, "shop/tasks.py": "pass\n"})

    result = inv.inventory(str(repo), None, 50)

    assert {s["stack"]: s["pack"] for s in result["stacks"]}.get("django") == "stacks/django.md"
    assert {"celery", "redis"} <= set(signals(result))
    assert result["coverage"]["unparsed_manifests"] == []


@pytest.mark.parametrize("cause", ["invalid-toml", "no-tomllib"])
def test_toml_fallback_keeps_the_manifest_visibly_unparsed(tmp_path: Path, monkeypatch, cause: str) -> None:
    text = '[project]\ndependencies = [\n  "django>=5",\n  "celery>=5",\n]\n'
    if cause == "invalid-toml":
        text += "[project]\n"
    else:
        monkeypatch.setattr(inv, "tomllib", None)
    repo = write(tmp_path / "shop", {"pyproject.toml": text})

    result = inv.inventory(str(repo), None, 50)

    assert "django" in stacks(result)
    assert "celery" in signals(result)
    assert result["coverage"]["unparsed_manifests"] == ["pyproject.toml"]
    assert any("regex fallback" in line for line in result["coverage"]["limitations"])


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs named pipes")
def test_special_files_are_reported_without_opening(tmp_path: Path) -> None:
    repo = write(tmp_path / "app", {"app.py": "pass\n"})
    target = write(tmp_path / "target", {"mix.exs": "defmodule T do\nend\n"})
    (repo / "run").mkdir()
    os.mkfifo(repo / "run/dev.fifo")
    os.mkfifo(repo / "AGENTS.md")
    os.mkfifo(target / "AGENTS.md")
    out = tmp_path / "inventory.json"

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(repo), "--target", str(target), "--json", str(out)],
        capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL,
    )

    assert proc.returncode == 0, proc.stderr
    coverage = json.loads(out.read_text(encoding="utf-8"))["coverage"]
    assert coverage["skipped_special_files"] == [
        {"path": "AGENTS.md", "type": "fifo"}, {"path": "run/dev.fifo", "type": "fifo"},
    ]
    assert "special files not read" in proc.stdout


def snapshot(root: Path) -> dict[str, tuple]:
    """Bytes, size and mtime of every file and directory under root, .git included."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            path = Path(dirpath, name)
            st = path.lstat()
            data = path.read_bytes() if path.is_file() and not path.is_symlink() else None
            out[str(path.relative_to(root))] = (data, st.st_size, st.st_mtime_ns)
    return out


@pytest.mark.parametrize("split", [False, True], ids=["ordinary-index", "split-index"])
def test_inventory_writes_nothing_in_a_git_checkout(tmp_path: Path, split: bool) -> None:
    repo = git_repo(tmp_path / "app", {"app.py": "a = 1\n", "lib/b.py": "b = 2\n"})
    (repo / "app.py").write_text("a = 3\n", encoding="utf-8")
    (repo / "new.py").write_text("n = 1\n", encoding="utf-8")
    os.utime(repo / "lib/b.py", ns=(0, 0))
    if split:
        git_cmd(repo, "update-index", "--split-index")
        for path in (repo / ".git").glob("sharedindex.*"):
            os.utime(path, ns=(0, 0))
    before = snapshot(repo)
    out = tmp_path / "inventory.json"

    proc = subprocess.run([sys.executable, str(SCRIPT), str(repo), "--json", str(out)],
                          capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)

    assert proc.returncode == 0, proc.stderr
    assert snapshot(repo) == before
    result = json.loads(out.read_text(encoding="utf-8"))
    git_info = result["source"]["git"]
    assert git_info["sha"] == git_cmd(repo, "rev-parse", "HEAD").stdout.strip()
    if split:
        assert any((repo / ".git").glob("sharedindex.*"))
        assert (git_info["dirty"], git_info["dirty_fingerprint"]) == (None, None)
        assert any("split index" in line for line in result["coverage"]["limitations"])
        assert "dirty state unknown" in proc.stdout
    else:
        assert git_info["dirty_files"] == ["app.py", "new.py"]


def oracles_of(root: Path, *oracle_dirs: Path) -> dict:
    return inv.inventory(str(root), None, 50, (), [str(d) for d in oracle_dirs])["oracles"]


@pytest.mark.parametrize(
    ("files", "kind", "cases"),
    [
        ({"tests/test_api.py": "def test_a():\n    pass\n\nasync def test_b():\n    pass\n"}, "pytest", 2),
        ({"tests/test_math.py": "import unittest\nclass T(unittest.TestCase):\n    def test_add(self): pass\n"},
         "unittest", 1),
        ({"blog/tests.py": "from django.test import TestCase\nclass T(TestCase):\n"
                           "    def test_list(self): pass\n    def test_detail(self): pass\n"}, "django", 2),
        ({"spec/models/user_spec.rb": "RSpec.describe User do\n  it \"saves\" do\n  end\n  it 'validates' do\n"
                                      "  end\nend\n"}, "rspec", 2),
        ({"test/models/user_test.rb": "class UserTest < ActiveSupport::TestCase\n  test \"saves\" do\n  end\n"
                                      "  def test_name; end\nend\n"}, "minitest", 2),
        ({"package.json": json.dumps({"devDependencies": {"jest": "29"}}),
          "src/sum.test.ts": "it('adds', () => {})\ntest.each([1])('x %i', () => {})\nit.skip('later', () => {})\n"
                             "regex.test(value)\n"}, "jest", 3),
        ({"src/sum.test.ts": "import { it, expect } from 'vitest'\nit('adds', () => {})\n"}, "vitest", 1),
        ({"src/sum.test.js": "it('adds', () => {})\n"}, "jest/vitest/mocha", 1),
        ({"pkg/sum_test.go": "package pkg\nfunc TestSum(t *testing.T) {}\nfunc TestNeg(tt *testing.T) {}\n"}, "go-test", 2),
        ({"tests/Unit/SumTest.php": "<?php\nclass SumTest extends TestCase {\n  public function testAdds() {}\n"
                                    "  /** @test */\n  public function it_subtracts() {}\n  #[Test]\n"
                                    "  public function multiplies() {}\n}\n"}, "phpunit", 3),
        ({"tests/Feature/SumTest.php": "<?php\nit('adds', function () {});\ntest('subtracts', fn () => 1);\n"},
         "pest", 2),
        ({"src/test/java/SumTest.java": "class SumTest {\n  @Test void adds() {}\n  @ParameterizedTest void many() {}\n"
                                        "  @TestFactory Stream<DynamicTest> dyn() {}\n}\n"}, "junit", 2),
        ({"tests/SumTests.cs": "public class SumTests {\n  [Fact] public void Adds() {}\n"
                               "  [Theory] public void Many() {}\n}\n"}, "xunit", 2),
        ({"tests/SumTests.cs": "[TestFixture]\npublic class SumTests {\n  [Test] public void Adds() {}\n}\n"}, "nunit", 1),
        ({"test/sum_test.exs": "defmodule SumTest do\n  use ExUnit.Case\n  test \"adds\" do\n  end\nend\n"}, "exunit", 1),
        ({"src/lib.rs": "#[cfg(test)]\nmod tests {\n    #[test]\n    fn adds() {}\n    #[tokio::test]\n"
                        "    async fn later() {}\n}\n"}, "rust-test", 2),
    ],
    ids=["pytest", "unittest", "django", "rspec", "minitest", "jest-from-deps", "vitest-import", "js-unresolved",
         "go", "phpunit", "pest", "junit", "xunit", "nunit", "exunit", "rust-inline"],
)
def test_oracle_tests_by_framework(tmp_path: Path, files: dict[str, str], kind: str, cases: int) -> None:
    tests = oracles_of(write(tmp_path / "app", files))["tests"]

    assert list(tests["frameworks"]) == [kind]
    assert tests["frameworks"][kind]["cases_approx"] == cases
    assert (tests["files"], tests["cases_approx"]) == (1, cases)


def test_django_tests_py_is_a_test_entry_point(tmp_path: Path) -> None:
    repo = write(tmp_path / "app", {"blog/tests.py": "# cache because slow\ndef test_x(): pass\n",
                                    "blog/views.py": "def index(request): pass\n"})

    result = inv.inventory(str(repo), None, 50)

    assert result["entry_points"]["tests"] == ["blog/tests.py"]
    assert not any(w.startswith("blog/tests.py") for w in result["why_comments"])


def test_go_benchmarks_are_not_counted_as_tests(tmp_path: Path) -> None:
    repo = write(tmp_path / "svc", {
        "go.mod": "module example.com/svc\n",
        "sum.go": "package svc\n",
        "sum_test.go": "package svc\nfunc TestSum(t *testing.T) {}\nfunc BenchmarkSum(b *testing.B) {}\n",
        "bench_test.go": "package svc\nfunc BenchmarkA(b *testing.B) {}\nfunc BenchmarkB(b *testing.B) {}\n",
    })

    o = oracles_of(repo)

    assert o["tests"]["frameworks"]["go-test"] == {"files": 1, "sample": ["sum_test.go"], "cases_approx": 1}
    assert o["benchmarks"]["go-bench"]["files"] == 2
    assert o["benchmarks"]["go-bench"]["cases_approx"] == 3
    assert o["tests"]["files_without_cases"] == 0
    assert o["grade"]["performance"] == "harness"


def test_pytest_benchmark_fixture_is_both_a_test_and_a_harness(tmp_path: Path) -> None:
    repo = write(tmp_path / "app", {"tests/test_perf.py": "def test_sort(benchmark):\n    benchmark(sorted, [3, 1])\n\n"
                                                         "def test_plain():\n    pass\n"})

    o = oracles_of(repo)

    assert o["tests"]["frameworks"]["pytest"]["cases_approx"] == 2
    assert o["benchmarks"]["pytest-benchmark"]["cases_approx"] == 1


HURL = """# Register
POST {{host}}/api/users
{"user": {"email": "a@b.c"}}
HTTP 201
[Captures]
token: jsonpath "$.user.token"

# Read it back
GET {{host}}/api/user
Authorization: Token {{token}}
HTTP 200
[Asserts]
# the profile echoes the email
jsonpath "$.user.email" == "a@b.c"

jsonpath "$.user.token" isString

DELETE {{host}}/api/user
HTTP 204
"""


def test_hurl_requests_and_asserts_are_counted_without_a_language(tmp_path: Path) -> None:
    repo = write(tmp_path / "app", {"api/users.hurl": HURL})

    hurl = oracles_of(repo)["black_box"]["hurl"]

    assert (hurl["files"], hurl["requests_approx"], hurl["asserts_approx"]) == (1, 3, 2)


@pytest.mark.parametrize(
    ("files", "family", "kind", "metrics"),
    [
        ({"api.postman_collection.json": '{"item": [{"request": {}}, {"request": {}}]}'},
         "black_box", "postman", {"requests_approx": 2}),
        ({"qa/api.json": '{"info": {"schema": "https://schema.getpostman.com/json/collection/v2.1.0/"},'
                         ' "item": [{"request": {}}]}'}, "black_box", "postman", {"requests_approx": 1}),
        ({"bruno/bruno.json": "{}", "bruno/login.bru": "meta {\n  name: Login\n}\n\npost {\n  url: {{host}}\n}\n\n"
                                                        "assert {\n  res.status: eq 200\n  res.body.token: isString\n}\n"},
         "black_box", "bruno", {"files": 1, "configs": 1, "requests_approx": 1, "asserts_approx": 2}),
        ({"requests.http": "GET http://localhost/api/tags\n\n###\n\nPOST http://localhost/api/users\n"},
         "black_box", "rest-client", {"requests_approx": 2}),
        ({"tests/test_users.tavern.yaml": "test_name: users\nstages:\n  - name: list\n    request:\n      url: x\n"},
         "black_box", "tavern", {"requests_approx": 1}),
        ({"dredd.yml": "blueprint: openapi.yml\n"}, "black_box", "dredd", {"files": 1}),
        ({"playwright.config.ts": "export default {}\n",
          "tests/login.spec.ts": "import { test } from '@playwright/test'\ntest('logs in', async () => {})\n"},
         "e2e", "playwright", {"files": 1, "configs": 1, "cases_approx": 1}),
        ({"cypress.config.js": "module.exports = {}\n", "cypress/e2e/login.cy.js": "it('logs in', () => {})\n"},
         "e2e", "cypress", {"files": 1, "configs": 1, "cases_approx": 1}),
        ({"spec/system/login_spec.rb": "RSpec.describe 'login' do\n  scenario 'works' do\n  end\nend\n"},
         "e2e", "capybara", {"cases_approx": 1}),
        ({"tests/Browser/LoginTest.php": "<?php\nclass LoginTest extends DuskTestCase {\n"
                                         "  public function testLogin() {}\n}\n"}, "e2e", "dusk", {"cases_approx": 1}),
        ({"features/login.feature": "Feature: Login\n  Scenario: ok\n  Scenario Outline: many\n"},
         "e2e", "gherkin", {"cases_approx": 2}),
        ({"load/smoke.js": "import http from 'k6/http'\nexport default function () {}\n"}, "benchmarks", "k6", {}),
        ({"locustfile.py": "from locust import HttpUser\n"}, "benchmarks", "locust", {}),
        ({"wrk/post.lua": "wrk.method = \"POST\"\n"}, "benchmarks", "wrk", {}),
        ({"perf/plan.jmx": "<jmeterTestPlan/>\n"}, "benchmarks", "jmeter", {}),
        ({"src/test/scala/BasicSimulation.scala": "class BasicSimulation extends Simulation\n"},
         "benchmarks", "gatling", {}),
        ({"load.yml": "config:\n  target: http://localhost\nscenarios:\n  - flow: []\n"}, "benchmarks", "artillery", {}),
        ({"src/main/java/SumBench.java": "class SumBench {\n  @Benchmark public void sum() {}\n"
                                         "  @BenchmarkMode(Mode.All) void x() {}\n}\n"},
         "benchmarks", "jmh", {"cases_approx": 1}),
        ({"script/bench.rb": "require 'benchmark/ips'\nBenchmark.ips { |x| }\n"}, "benchmarks", "benchmark-ips", {}),
        ({"phpbench.json": "{}", "benchmarks/SumBench.php": "<?php\nclass SumBench {\n  public function benchSum() {}\n}\n"},
         "benchmarks", "phpbench", {"files": 1, "configs": 1, "cases_approx": 1}),
        ({"benches/sum.rs": "fn bench(c: &mut Criterion) {}\ncriterion_group!(benches, bench);\n"},
         "benchmarks", "criterion", {}),
        ({"src/sum.bench.ts": "bench('sum', () => {})\n"}, "benchmarks", "js-bench", {}),
        ({"bench/run.exs": "Benchee.run(%{\"sum\" => fn -> 1 end})\n"}, "benchmarks", "benchee", {}),
        ({"bench/run.sh": "#!/bin/sh\n", "bench/README.md": "# notes\n"}, "benchmarks", "bench-dir", {"files": 1}),
        ({"docs/openapi.yaml": "openapi: 3.0.0\n"}, "api_contracts", "openapi", {}),
        ({"api/spec.json": '{"swagger": "2.0"}'}, "api_contracts", "openapi", {}),
        ({"schema.graphql": "type Query { a: Int }\n"}, "api_contracts", "graphql", {}),
        ({"proto/user.proto": "syntax = \"proto3\";\n"}, "api_contracts", "protobuf", {}),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_oracle_families_detect_each_kind(tmp_path: Path, files: dict[str, str], family: str, kind: str,
                                          metrics: dict[str, int]) -> None:
    entry = oracles_of(write(tmp_path / "app", files))[family][kind]

    assert entry["files"] == metrics.get("files", 1)
    assert {k: entry[k] for k in metrics if k != "files"} == {k: v for k, v in metrics.items() if k != "files"}


def test_e2e_files_are_not_unit_tests_and_configs_alone_are_no_suite(tmp_path: Path) -> None:
    repo = write(tmp_path / "app", {
        "package.json": json.dumps({"devDependencies": {"jest": "29"}}),
        "playwright.config.ts": "export default {}\n",
        "e2e/login.spec.ts": "import { test } from '@playwright/test'\ntest('logs in', async () => {})\n",
    })

    o = oracles_of(repo)

    assert o["tests"]["files"] == 0
    assert o["e2e"]["playwright"]["files"] == 1
    assert o["grade"]["inputs"]["suites"] == ["playwright: 1 file, ~1 case, 1 config"]
    (repo / "e2e/login.spec.ts").unlink()
    assert oracles_of(repo)["grade"]["inputs"]["suites"] == []


def test_coverage_config_is_listed_by_path_only(tmp_path: Path) -> None:
    repo = write(tmp_path / "app", {
        ".coveragerc": "[run]\n", "pyproject.toml": "[tool.coverage.run]\nbranch = true\n",
        "codecov.yml": "coverage: {}\n", ".simplecov": "SimpleCov.start\n", ".nycrc.json": "{}",
        "jest.config.js": "module.exports = { coverageThreshold: { global: { lines: 80 } } }\n",
        "phpunit.xml.dist": "<phpunit><coverage/></phpunit>\n", "jest.setup.js": "// coverageThreshold\n",
    })

    cov = oracles_of(repo)["coverage_config"]

    assert {k: e["sample"] for k, e in cov.items()} == {
        "codecov": ["codecov.yml"], "coverage.py": [".coveragerc", "pyproject.toml"],
        "jest-coverage-threshold": ["jest.config.js"], "nyc": [".nycrc.json"],
        "phpunit-coverage": ["phpunit.xml.dist"], "simplecov": [".simplecov"],
    }
    assert "percentage unknown" in inv.to_markdown(inv.inventory(str(repo), None, 50))


@pytest.mark.parametrize(
    ("source_files", "source_tests", "external_tests", "suites", "grade"),
    [
        (10, 0, 0, [], "none"),
        (10, 2, 0, [], "weak"),
        (100, 4, 0, [], "weak"),
        (2, 1, 0, [], "weak"),
        (100, 5, 0, [], "moderate"),
        (20, 3, 0, [], "moderate"),
        (10, 0, 0, ["hurl: 1 file"], "moderate"),
        (100, 4, 0, ["hurl: 1 file"], "moderate"),
        (10, 3, 0, [], "strong"),
        (100, 5, 0, ["hurl: 1 file"], "strong"),
        (100, 2, 3, ["hurl (external): 1 file"], "strong"),
    ],
)
def test_oracle_grade_boundaries(source_files: int, source_tests: int, external_tests: int,
                                 suites: list[str], grade: str) -> None:
    result = inv.oracle_grade(source_files, source_tests, external_tests, suites, [])

    assert result["correctness"] == grade
    assert result["performance"] == "none"
    weak_at = result["thresholds"]["weak_threshold"]
    assert weak_at == max(3, -(-5 * source_files // 100))
    assert any(f"= {weak_at} test files" in reason for reason in result["reasons"])
    assert any(f"correctness {grade}:" in reason for reason in result["reasons"])


def test_oracle_grade_names_the_harness_and_the_crossed_threshold() -> None:
    result = inv.oracle_grade(100, 4, 0, [], ["k6: 2 files"])

    assert result["performance"] == "harness"
    assert "weak threshold max(3, 5% of 100 source files) = 5 test files: 4 < 5" in result["reasons"]
    assert any("k6: 2 files" in r and "not a baseline" in r for r in result["reasons"])


def test_grade_counts_source_files_outside_tests(tmp_path: Path) -> None:
    files = {f"app/m{i}.py": "x = 1\n" for i in range(10)}
    files.update({f"tests/test_{i}.py": "def test_x(): pass\n" for i in range(3)})
    files.update({"bench/load.py": "x = 1\n", "tests/conftest.py": "import pytest\n"})

    o = oracles_of(write(tmp_path / "app", files))

    assert o["grade"]["inputs"]["source_files"] == 10
    assert o["tests"]["files_without_cases"] == 1
    assert (o["grade"]["correctness"], o["grade"]["inputs"]["test_ratio"]) == ("strong", 0.3)


@pytest.fixture
def api_with_external_suite(tmp_path: Path) -> tuple[Path, Path]:
    files = {f"api/m{i}.py": "x = 1\n" for i in range(20)}
    files.update({f"tests/test_{i}.py": "def test_x(): pass\n" for i in range(3)})
    source = write(tmp_path / "legacy", files)
    suite = write(tmp_path / "spec", {"hurl/users.hurl": HURL, "openapi.yml": "openapi: 3.0.0\n",
                                      "tests/test_contract.py": "def test_a(): pass\n"})
    return source, suite


def test_external_oracle_counts_in_grade_but_not_in_source_identity(api_with_external_suite) -> None:
    source, suite = api_with_external_suite

    plain = inv.inventory(str(source), None, 50)
    graded = inv.inventory(str(source), None, 50, (), [str(suite)])
    ext = graded["oracles"]["external"]

    assert plain["oracles"]["grade"]["correctness"] == "moderate"
    assert graded["oracles"]["grade"]["correctness"] == "strong"
    assert graded["oracles"]["grade"]["inputs"]["external_test_files"] == 1
    assert graded["source"]["tree_fingerprint"] == plain["source"]["tree_fingerprint"]
    assert inv.compare(plain, graded) == []
    assert [(e["root"], e["external"]) for e in ext] == [(os.path.realpath(suite), True)]
    assert ext[0]["black_box"]["hurl"] == {"files": 1, "sample": ["hurl/users.hurl"], "external": True,
                                           "requests_approx": 3, "asserts_approx": 2}
    assert ext[0]["api_contracts"]["openapi"]["external"] is True
    assert graded["oracles"]["black_box"] == {}
    md = inv.to_markdown(graded)
    assert f"- external `{os.path.realpath(suite)}` (fingerprint `{ext[0]['tree_fingerprint']}`" in md
    assert "hurl (external): 1 file, ~3 requests, ~2 asserts" in md


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs named pipes")
def test_external_oracle_writes_nothing_and_opens_no_links_or_fifos(api_with_external_suite, tmp_path: Path) -> None:
    source, suite = api_with_external_suite
    secret = write(tmp_path / "outside", {"leak.hurl": "GET http://secret.example/never-read\n"})
    (suite / "linked.hurl").symlink_to(secret / "leak.hurl")
    (suite / "linked-dir").symlink_to(secret, target_is_directory=True)
    os.mkfifo(suite / "pipe.hurl")
    before = (snapshot(source), snapshot(suite))
    out = tmp_path / "out"

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(source), "--oracle", str(suite), "--json", str(out / "i.json"),
         "--md", str(out / "i.md")],
        capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL,
    )

    assert proc.returncode == 0, proc.stderr
    assert (snapshot(source), snapshot(suite)) == before
    ext = json.loads((out / "i.json").read_text(encoding="utf-8"))["oracles"]["external"][0]
    assert {link["path"] for link in ext["skipped_symlinks"]} == {"linked.hurl", "linked-dir"}
    assert ext["skipped_special_files"] == [{"path": "pipe.hurl", "type": "fifo"}]
    assert ext["black_box"]["hurl"]["files"] == 1
    assert "never-read" not in proc.stdout
    assert "--oracle dirs: 2 symlinks not followed and 1 special file not read" in proc.stdout


def test_cli_refuses_to_write_inside_an_oracle_dir_or_take_a_file(api_with_external_suite, capsys) -> None:
    source, suite = api_with_external_suite

    assert inv.main([str(source), "--oracle", str(suite), "--md", str(suite / "inv.md")]) == 2
    assert not (suite / "inv.md").exists()
    assert inv.main([str(source), "--oracle", str(suite / "openapi.yml")]) == 2
    assert "not a directory" in capsys.readouterr().err


def test_oracle_dir_inside_source_or_holding_it_is_scanned_once(tmp_path: Path) -> None:
    repo = tmp_path / "port"
    source = write(repo / "reference", {"app.py": "x = 1\n", "specs/users.hurl": HURL})
    write(repo, {"specs/extra.hurl": "GET http://localhost/api/tags\n"})

    inner = oracles_of(source, source / "specs", source / "specs")
    outer = oracles_of(source, repo, repo / "specs")

    assert inner["black_box"]["hurl"]["files"] == 1
    assert inner["external"] == [{"root": os.path.realpath(source / "specs"), "external": False,
                                  "inside_source": True, "note": "inside SOURCE: already scanned as part of it"}]
    assert outer["external"][0]["black_box"]["hurl"]["sample"] == ["specs/extra.hurl"]
    assert outer["external"][1]["inside_oracle"] == os.path.realpath(repo)


def test_markdown_renders_the_oracles_section(express_app: Path) -> None:
    md = inv.to_markdown(inv.inventory(str(express_app), None, 50))
    section = md.split("## Oracles", 1)[1].split("\n## ", 1)[0]

    assert "- grade: correctness **weak**, performance **none**" in section
    assert "  - 1 test file (1 in SOURCE, 0 external) vs 2 source files: ratio 0.50" in section
    assert "- tests: 1 file, ~1 case" in section
    assert "  - jest: 1 file, ~1 case — src/routes/api/__tests__/users.test.ts" in section
    assert "- black-box API suites: none" in section
    assert "- external oracles: none" in section


def test_compare_accepts_an_inventory_from_before_oracles(rails_app: Path, tmp_path: Path, capsys) -> None:
    prev = tmp_path / "prev.json"
    assert inv.main([str(rails_app), "--json", str(prev)]) == 0
    old = json.loads(prev.read_text(encoding="utf-8"))
    del old["oracles"]
    old["version"] = 2
    prev.write_text(json.dumps(old), encoding="utf-8")
    capsys.readouterr()

    assert inv.main([str(rails_app), "--compare", str(prev)]) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "unchanged"
    assert "inventory version 2" in captured.err

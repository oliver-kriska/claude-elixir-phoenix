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
    assert data["version"] == 2
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
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
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

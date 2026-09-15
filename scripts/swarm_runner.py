"""Executable local orchestrator for the eleven-agent Hixton engineering swarm.

The runner uses the user's normal Codex/ChatGPT CLI login. It never imports the
trading runtime, never reads ignored operator data, and runs all agent work in a
clean disposable Git worktree. Only a fully gated mission branch is fast-forwarded
back to the user's current GPT working branch.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable
import uuid

from scripts.swarm_core import (
    AGENT_IDS,
    SwarmContractError,
    agent_prompt_contract,
    completion_from_reports,
    heartbeat,
    known_regression_requirements,
    load_json,
    load_mission,
    mark_done,
    new_runtime,
    path_in_scope,
    record_attempt,
    reopen_round,
    required_agents,
    utc_now_text,
    validate_patch_paths,
    validate_plan,
    validate_registry,
    validate_report,
    write_json,
)

TARGET_REPOSITORY_MARKER = "127027/Der-Hixton-von-GPT"
DEFAULT_TIMEOUT_MINUTES = 20
DEFAULT_AGENT_RETRIES = 2
DEFAULT_MAX_ROUNDS = 8


class CommandError(RuntimeError):
    pass


def run(
    args: list[str],
    *,
    cwd: Path,
    check: bool = True,
    capture: bool = True,
    timeout: float | None = None,
    stdout: Any | None = None,
    stderr: Any | None = None,
) -> subprocess.CompletedProcess[str]:
    kwargs: dict[str, Any] = {
        "cwd": str(cwd),
        "text": True,
        "timeout": timeout,
        "check": False,
    }
    if stdout is not None:
        kwargs["stdout"] = stdout
    elif capture:
        kwargs["stdout"] = subprocess.PIPE
    if stderr is not None:
        kwargs["stderr"] = stderr
    elif capture:
        kwargs["stderr"] = subprocess.STDOUT
    result = subprocess.run(args, **kwargs)
    if check and result.returncode != 0:
        output = result.stdout if isinstance(result.stdout, str) else ""
        raise CommandError(f"Command failed ({result.returncode}): {' '.join(args)}\n{output}")
    return result


def git(repo: Path, *args: str, check: bool = True) -> str:
    result = run(["git", *args], cwd=repo, check=check)
    return (result.stdout or "").strip()


def current_branch(repo: Path) -> str:
    branch = git(repo, "branch", "--show-current")
    if not branch:
        raise CommandError("Swarm runner requires a named current branch, not detached HEAD")
    return branch


def ensure_target_repository(repo: Path) -> str:
    origin = git(repo, "remote", "get-url", "origin")
    normalized = origin.replace("\\", "/").removesuffix(".git")
    if TARGET_REPOSITORY_MARKER not in normalized:
        raise CommandError(
            "Safety stop: this swarm runner is intentionally restricted to "
            f"{TARGET_REPOSITORY_MARKER}; origin is {origin!r}"
        )
    return origin


def require_clean(repo: Path) -> None:
    status = git(repo, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise CommandError(
            "Working tree must be clean before starting the swarm. Commit/stash first:\n" + status
        )


def require_engineering_ready(repo: Path) -> dict[str, Any]:
    state = load_json(repo / "agent_memory" / "state.json")
    if not state.get("bootstrap_complete") or state.get("progress_percent") != 100:
        raise CommandError(
            "AGENTS.md bootstrap is not complete; the swarm may not modify engineering files yet."
        )
    if state.get("unresolved_repository_questions"):
        raise CommandError("Repository-understanding questions are still unresolved")
    return state


def locate_codex() -> str:
    for name in ("codex.cmd", "codex") if os.name == "nt" else ("codex", "codex.cmd"):
        found = shutil.which(name)
        if found:
            return found
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm") or shutil.which("npm")
    if npm:
        result = subprocess.run(
            [npm, "config", "get", "prefix"], text=True, capture_output=True, check=False
        )
        if result.returncode == 0:
            prefix = result.stdout.strip()
            candidate = Path(prefix) / ("codex.cmd" if os.name == "nt" else "bin/codex")
            if candidate.exists():
                return str(candidate)
    raise CommandError(
        "Codex CLI not found. Install it with npm install -g @openai/codex@latest and use normal ChatGPT/Codex login."
    )


def safe_slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    return "-".join(part for part in cleaned.split("-") if part)[:50] or "mission"


def changed_paths(repo: Path) -> tuple[str, ...]:
    text = git(repo, "status", "--porcelain", "--untracked-files=all")
    result: list[str] = []
    for raw in text.splitlines():
        if len(raw) < 4:
            continue
        path = raw[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        result.append(path.replace("\\", "/"))
    return tuple(result)


def commit_all(repo: Path, message: str) -> str | None:
    if not changed_paths(repo):
        return None
    git(repo, "add", "-A")
    staged = git(repo, "diff", "--cached", "--name-only")
    if not staged:
        return None
    git(
        repo,
        "-c",
        "user.name=Hixton Agent Swarm",
        "-c",
        "user.email=hixton-swarm@local.invalid",
        "commit",
        "-m",
        message,
    )
    return git(repo, "rev-parse", "HEAD")


def hard_restore(repo: Path) -> None:
    git(repo, "reset", "--hard", "HEAD")
    git(repo, "clean", "-fd")


@contextmanager
def mission_worktree(repo: Path, branch_name: str, work: Path):
    try:
        git(repo, "worktree", "add", "-b", branch_name, str(work), "HEAD")
        yield work
    finally:
        if work.exists():
            git(repo, "worktree", "remove", "--force", str(work), check=False)
            git(repo, "worktree", "prune", check=False)


def role_text(work: Path, agent_id: str, registry: dict[str, Any]) -> str:
    row = next(item for item in registry["agents"] if item["id"] == agent_id)
    return (work / "agent_memory" / "swarm" / row["role_file"]).read_text(encoding="utf-8")


def report_path(run_root: Path, round_no: int, agent: str, phase: str) -> Path:
    return run_root / f"round-{round_no:02d}" / f"{agent}_{phase}.json"


def report_relpath(work: Path, path: Path) -> str:
    return path.relative_to(work).as_posix()


def write_generated_report(
    path: Path,
    *,
    agent: str,
    mission_id: str,
    round_no: int,
    phase: str,
    verdict: str,
    summary: str,
    evidence: Iterable[str],
    findings: Iterable[str] = (),
    next_actions: Iterable[str] = (),
) -> dict[str, Any]:
    value = {
        "agent_id": agent,
        "mission_id": mission_id,
        "round": round_no,
        "phase": phase,
        "verdict": verdict,
        "summary": summary,
        "findings": list(findings),
        "evidence": list(evidence),
        "next_actions": list(next_actions),
    }
    write_json(path, value)
    return value


def run_codex(
    *,
    codex: str,
    work: Path,
    prompt: str,
    log_path: Path,
    timeout_minutes: int,
) -> tuple[int, bool]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        codex,
        "--sandbox",
        "workspace-write",
        "--ask-for-approval",
        "never",
        "--cd",
        str(work),
        prompt,
    ]
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        process = subprocess.Popen(
            command,
            cwd=str(work),
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            code = process.wait(timeout=max(60, timeout_minutes * 60))
            return code, False
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            return 124, True


def allowed_report_paths(*paths: Path, work: Path) -> tuple[str, ...]:
    return tuple(report_relpath(work, path) for path in paths)


def verify_report_only_changes(work: Path, allowed: Iterable[str]) -> tuple[bool, tuple[str, ...]]:
    changed = changed_paths(work)
    allowed_set = set(allowed)
    illegal = tuple(path for path in changed if path not in allowed_set)
    return not illegal, illegal


def run_role(
    *,
    codex: str,
    work: Path,
    registry: dict[str, Any],
    mission: dict[str, Any],
    plan: dict[str, Any] | None,
    run_root: Path,
    round_no: int,
    agent: str,
    phase: str,
    runtime: dict[str, Any],
    timeout_minutes: int,
    retries: int,
    patch_mode: bool = False,
    extra_prompt: str = "",
    extra_allowed_report_files: tuple[Path, ...] = (),
) -> dict[str, Any]:
    mission_id = str(mission["id"])
    path = report_path(run_root, round_no, agent, phase)
    rel = report_relpath(work, path)
    base_prompt = agent_prompt_contract(
        agent_id=agent,
        mission=mission,
        round_no=round_no,
        phase=phase,
        report_relpath=rel,
        role_text=role_text(work, agent, registry),
        plan=plan,
    )
    if patch_mode:
        assert plan is not None
        base_prompt += "\nYou are the sole patch owner for this round. You MAY modify only the explicit write_scope from A10's plan, plus your report file. Make the smallest root-cause change. Do not commit; the supervisor validates paths and commits after your run.\n"
    else:
        base_prompt += "\nYou are a reviewer in this phase. Do NOT modify source, tests, configuration, workflows, DMS or other repository files. Only write your required report file and any explicitly named coordinator JSON file.\n"
    if extra_prompt:
        base_prompt += "\n" + extra_prompt.strip() + "\n"

    for attempt in range(1, retries + 2):
        heartbeat(runtime, agent, "IN_PROGRESS")
        runtime_path = run_root / "runtime.json"
        write_json(runtime_path, runtime)
        commit_all(work, f"docs(agent): heartbeat {mission_id} {agent} {phase} attempt {attempt}")
        before = set(changed_paths(work))
        if before:
            raise CommandError(f"Internal error: worktree dirty before {agent}: {sorted(before)}")
        log_path = path.with_suffix(".log")
        code, timed_out = run_codex(
            codex=codex,
            work=work,
            prompt=base_prompt,
            log_path=log_path,
            timeout_minutes=timeout_minutes,
        )
        changed = changed_paths(work)
        report_allow = allowed_report_paths(path, *extra_allowed_report_files, work=work)
        if not patch_mode:
            okay, illegal = verify_report_only_changes(work, report_allow)
            if not okay:
                hard_restore(work)
                path.parent.mkdir(parents=True, exist_ok=True)
                generated = write_generated_report(
                    path,
                    agent=agent,
                    mission_id=mission_id,
                    round_no=round_no,
                    phase=phase,
                    verdict="FAIL" if agent not in {"A09", "A11"} else (
                        "QA_FAIL" if agent == "A09" else "GOVERNANCE_FAIL"
                    ),
                    summary="Agent changed repository files outside its reviewer/report scope.",
                    evidence=[f"Unauthorized paths: {', '.join(illegal)}"],
                    next_actions=["A10 must re-prompt/reassign the agent without unauthorized writes."],
                )
                commit_all(work, f"docs(agent): record scope violation by {agent}")
                return generated
        elif plan is not None:
            non_report = [path_name for path_name in changed if path_name not in set(report_allow)]
            try:
                validate_patch_paths(
                    non_report,
                    plan.get("write_scope") or [],
                    allow_live_release=bool(mission.get("allow_live_release", False)),
                )
            except SwarmContractError as exc:
                hard_restore(work)
                path.parent.mkdir(parents=True, exist_ok=True)
                generated = write_generated_report(
                    path,
                    agent=agent,
                    mission_id=mission_id,
                    round_no=round_no,
                    phase=phase,
                    verdict="FAIL",
                    summary="Patch owner violated the authorized file/live-release scope.",
                    evidence=[str(exc)],
                    next_actions=["A10 must narrow/reassign the patch and rerun the full round."],
                )
                commit_all(work, f"docs(agent): record patch scope violation by {agent}")
                return generated

        if code == 0 and path.exists():
            try:
                result = validate_report(
                    load_json(path),
                    agent_id=agent,
                    mission_id=mission_id,
                    round_no=round_no,
                    phase=phase,
                )
            except (SwarmContractError, json.JSONDecodeError) as exc:
                result = None
                validation_error = str(exc)
            else:
                validation_error = ""
            if result is not None:
                record_attempt(runtime, agent, verdict=result["verdict"], report_path=rel)
                write_json(run_root / "runtime.json", runtime)
                commit_all(
                    work,
                    f"{'fix' if patch_mode else 'docs'}(agent): {mission_id} {agent} {phase} round {round_no}",
                )
                return result
        else:
            validation_error = (
                "Codex process timed out" if timed_out else f"Codex exited with code {code}"
            )

        # Invalid/missing report is not silently accepted. Reset uncommitted work and
        # retry the same agent: this is the concrete "anstupsen" behavior.
        hard_restore(work)
        if attempt <= retries:
            time.sleep(1)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        verdict = "FAIL"
        if agent == "A09":
            verdict = "QA_FAIL"
        elif agent == "A11" and phase == "governance":
            verdict = "GOVERNANCE_FAIL"
        generated = write_generated_report(
            path,
            agent=agent,
            mission_id=mission_id,
            round_no=round_no,
            phase=phase,
            verdict=verdict,
            summary="Agent failed to produce a valid deliverable after automatic retries.",
            evidence=[validation_error, f"Attempts: {attempt}"],
            next_actions=["A10 must reassign/re-prompt this role in the next repair round."],
        )
        record_attempt(runtime, agent, verdict=verdict, report_path=rel, note="auto-retry exhausted")
        write_json(run_root / "runtime.json", runtime)
        commit_all(work, f"docs(agent): record stalled {agent} after retries")
        return generated

    raise AssertionError("unreachable")


def qa_commands(work: Path) -> list[tuple[str, list[str]]]:
    venv_python = work / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    python = str(venv_python) if venv_python.exists() else sys.executable
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm") or shutil.which("npm")
    commands: list[tuple[str, list[str]]] = [
        ("compileall", [python, "-m", "compileall", "-q", "src", "scripts"]),
        ("ruff", [python, "-m", "ruff", "check", "src", "tests", "scripts/swarm_core.py", "scripts/swarm_runner.py"]),
        ("mypy", [python, "-m", "mypy", "src"]),
        ("pytest", [python, "-m", "pytest", "-q"]),
    ]
    if (work / "ui" / "package.json").exists():
        if npm:
            commands.extend(
                [
                    ("ui-test", [npm, "--prefix", "ui", "test"]),
                    ("ui-typecheck", [npm, "--prefix", "ui", "run", "check"]),
                    ("ui-build", [npm, "--prefix", "ui", "run", "build"]),
                ]
            )
        else:
            commands.append(("ui-tooling", ["__MISSING_NPM__"]))
    return commands


def run_deterministic_qa(work: Path, run_root: Path, round_no: int) -> dict[str, Any]:
    qa_dir = run_root / f"round-{round_no:02d}"
    qa_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    passed = True
    for name, command in qa_commands(work):
        log_path = qa_dir / f"qa_{name}.log"
        if command[0] == "__MISSING_NPM__":
            records.append({"name": name, "returncode": 127, "log": report_relpath(work, log_path)})
            log_path.write_text("npm was not found; UI QA cannot be completed.\n", encoding="utf-8")
            passed = False
            continue
        with log_path.open("w", encoding="utf-8", errors="replace") as log:
            result = run(command, cwd=work, check=False, capture=False, stdout=log, stderr=log)
        records.append(
            {"name": name, "returncode": result.returncode, "log": report_relpath(work, log_path)}
        )
        if result.returncode != 0:
            passed = False
            # Continue to collect all gate failures rather than hiding later failures.
    result = {
        "passed": passed,
        "round": round_no,
        "created_at_utc": utc_now_text(),
        "commands": records,
    }
    result_path = qa_dir / "deterministic_qa.json"
    write_json(result_path, result)
    commit_all(work, f"test(agent): record deterministic QA round {round_no}")
    return result


def reports_for_completion(round_dir: Path) -> dict[str, dict[str, Any]]:
    reports: dict[str, dict[str, Any]] = {}
    for path in round_dir.glob("A*.json"):
        data = load_json(path)
        agent = str(data.get("agent_id"))
        phase = str(data.get("phase"))
        if agent == "A11" and phase == "governance":
            reports["A11:governance"] = data
        elif agent == "A11" and phase == "assignment_audit":
            reports["A11:assignment_audit"] = data
        else:
            reports[agent] = data
    return reports


def phase_prompt_context(run_root: Path, round_no: int) -> str:
    round_dir = run_root / f"round-{round_no:02d}"
    reports = sorted(path.relative_to(run_root.parent.parent.parent).as_posix() for path in round_dir.glob("*.json"))
    return "Available prior reports for this round:\n" + "\n".join(f"- {item}" for item in reports)


def run_round(
    *,
    codex: str,
    work: Path,
    registry: dict[str, Any],
    mission: dict[str, Any],
    run_root: Path,
    runtime: dict[str, Any],
    timeout_minutes: int,
    retries: int,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    round_no = int(runtime["round"])
    mission_id = str(mission["id"])
    round_dir = run_root / f"round-{round_no:02d}"
    plan_path = round_dir / "plan.json"

    # A10 planning: report + explicit machine-readable plan. No source patch yet.
    a10_report = report_path(run_root, round_no, "A10", "planning")
    run_role(
        codex=codex,
        work=work,
        registry=registry,
        mission=mission,
        plan=None,
        run_root=run_root,
        round_no=round_no,
        agent="A10",
        phase="planning",
        runtime=runtime,
        timeout_minutes=timeout_minutes,
        retries=retries,
        extra_allowed_report_files=(plan_path,),
        extra_prompt=f"""
Create a second JSON file exactly at {report_relpath(work, plan_path)} with fields:
mission_id, required_agents, patch_owner (agent id or null), write_scope[] repository-relative prefixes, affected_domains[], security_sensitive boolean.
All 11 agents are consulted when required by taskboard. Pick only one patch_owner. A01/A06/A09/A11 may never be patch owner. A10 may be patch owner only if taskboard allow_coordinator_patch=true for agent-governance infrastructure.
Do not widen scope merely for convenience. No live-release path unless taskboard explicitly allow_live_release=true.
""",
    )
    if not plan_path.exists():
        raise CommandError("A10 did not create plan.json after a valid planning report")
    plan = load_json(plan_path)
    validate_plan(
        plan,
        mission,
        allow_coordinator_patch=bool(mission.get("allow_coordinator_patch", False)),
    )
    commit_all(work, f"docs(agent): validate {mission_id} plan round {round_no}")

    # A01 mandatory documentary/requirement preflight.
    run_role(
        codex=codex,
        work=work,
        registry=registry,
        mission=mission,
        plan=plan,
        run_root=run_root,
        round_no=round_no,
        agent="A01",
        phase="preflight",
        runtime=runtime,
        timeout_minutes=timeout_minutes,
        retries=retries,
        extra_prompt=phase_prompt_context(run_root, round_no),
    )

    # A11 audits A10's assignment before anyone may patch.
    assignment = run_role(
        codex=codex,
        work=work,
        registry=registry,
        mission=mission,
        plan=plan,
        run_root=run_root,
        round_no=round_no,
        agent="A11",
        phase="assignment_audit",
        runtime=runtime,
        timeout_minutes=timeout_minutes,
        retries=retries,
        extra_prompt=phase_prompt_context(run_root, round_no)
        + "\nAudit A10's agent coverage, one-patch-owner separation and write scope. Use PASS/FAIL/BLOCKED in this early audit, not GOVERNANCE_PASS.",
    )
    if assignment["verdict"] not in {"PASS", "NOT_APPLICABLE"}:
        return plan, reports_for_completion(round_dir)

    patch_owner = plan.get("patch_owner")
    specialist_order = ("A07", "A08", "A02", "A03", "A04", "A05")
    for agent in specialist_order:
        if agent not in required_agents(mission):
            continue
        is_owner = agent == patch_owner
        run_role(
            codex=codex,
            work=work,
            registry=registry,
            mission=mission,
            plan=plan,
            run_root=run_root,
            round_no=round_no,
            agent=agent,
            phase="implementation" if is_owner else "review",
            runtime=runtime,
            timeout_minutes=timeout_minutes,
            retries=retries,
            patch_mode=is_owner,
            extra_prompt=phase_prompt_context(run_root, round_no),
        )

    # Agent-governance infrastructure is A10's domain; if A10 is the authorized
    # patch owner, let it implement only after independent A01/A11 plan audit.
    if patch_owner == "A10":
        run_role(
            codex=codex,
            work=work,
            registry=registry,
            mission=mission,
            plan=plan,
            run_root=run_root,
            round_no=round_no,
            agent="A10",
            phase="implementation",
            runtime=runtime,
            timeout_minutes=timeout_minutes,
            retries=retries,
            patch_mode=True,
            extra_prompt=phase_prompt_context(run_root, round_no)
            + "\nImplement only the agent-governance/tooling change from your already-audited plan. You still cannot approve it.",
        )

    # Every patch/no-patch mission gets a cross-component regression review.
    run_role(
        codex=codex,
        work=work,
        registry=registry,
        mission=mission,
        plan=plan,
        run_root=run_root,
        round_no=round_no,
        agent="A06",
        phase="regression",
        runtime=runtime,
        timeout_minutes=timeout_minutes,
        retries=retries,
        extra_prompt=phase_prompt_context(run_root, round_no),
    )

    qa = run_deterministic_qa(work, run_root, round_no)
    run_role(
        codex=codex,
        work=work,
        registry=registry,
        mission=mission,
        plan=plan,
        run_root=run_root,
        round_no=round_no,
        agent="A09",
        phase="qa",
        runtime=runtime,
        timeout_minutes=timeout_minutes,
        retries=retries,
        extra_prompt=phase_prompt_context(run_root, round_no)
        + f"\nDeterministic QA result is passed={qa['passed']}. Inspect its JSON/logs. You MUST return QA_FAIL if deterministic QA did not pass or required evidence is missing.",
    )

    run_role(
        codex=codex,
        work=work,
        registry=registry,
        mission=mission,
        plan=plan,
        run_root=run_root,
        round_no=round_no,
        agent="A11",
        phase="governance",
        runtime=runtime,
        timeout_minutes=timeout_minutes,
        retries=retries,
        extra_prompt=phase_prompt_context(run_root, round_no)
        + "\nFinal governance: verify every required role actually delivered, no evidence was invalidated by a later patch, A09 is independent, known regression obligations were addressed, and the result matches the owner's original objective. Do not override QA_FAIL.",
    )
    return plan, reports_for_completion(round_dir)


def finalize_mission_in_taskboard(work: Path, mission_id: str) -> None:
    path = work / "agent_memory" / "swarm" / "taskboard.json"
    board = load_json(path)
    active = board.get("active_mission")
    if isinstance(active, dict) and active.get("id") == mission_id:
        active["state"] = "DONE"
        active["completed_at_utc"] = utc_now_text()
    for item in board.get("queued_missions") or []:
        if isinstance(item, dict):
            blockers = item.get("blocked_by") or []
            if mission_id in blockers:
                item["blocked_by"] = [value for value in blockers if value != mission_id]
                if not item["blocked_by"] and item.get("state") == "BLOCKED":
                    item["state"] = "NEW"
    write_json(path, board)
    commit_all(work, f"docs(agent): close {mission_id} and unblock dependent missions")


def self_test(repo: Path) -> None:
    registry = validate_registry(repo)
    mission = load_mission(repo, "SWARM-001")
    if len(registry["agents"]) != 11:
        raise CommandError("Self-test: expected 11 agents")
    if required_agents(mission) != AGENT_IDS:
        raise CommandError("Self-test: SWARM-001 must require all 11 agents")
    regression = known_regression_requirements(mission)
    if "USDT_USDC_MIGRATION" not in regression:
        raise CommandError("Self-test: migration incident is not registered on SWARM-001")
    print("Swarm self-test PASS: 11 agents, mandatory gates and migration regression registered.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local eleven-agent Hixton engineering swarm")
    parser.add_argument("--mission", default="SWARM-001")
    parser.add_argument("--max-rounds", type=int, default=DEFAULT_MAX_ROUNDS)
    parser.add_argument("--agent-timeout-minutes", type=int, default=DEFAULT_TIMEOUT_MINUTES)
    parser.add_argument("--agent-retries", type=int, default=DEFAULT_AGENT_RETRIES)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--no-push", action="store_true", help="merge locally but do not push origin")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = Path(__file__).resolve().parents[1]
    ensure_target_repository(repo)
    require_engineering_ready(repo)
    validate_registry(repo)
    if args.self_test:
        self_test(repo)
        return 0
    if args.max_rounds < 1 or args.agent_retries < 0 or args.agent_timeout_minutes < 1:
        raise CommandError("Round/retry/timeout values must be positive (retries may be zero)")
    require_clean(repo)
    branch = current_branch(repo)
    git(repo, "pull", "--ff-only", "origin", branch)
    require_clean(repo)
    mission = load_mission(repo, args.mission)
    if mission.get("state") == "DONE":
        print(f"Mission {args.mission} is already DONE.")
        return 0
    blockers = mission.get("blocked_by") or []
    if blockers:
        raise CommandError(f"Mission {args.mission} is blocked by: {blockers}")
    codex = locate_codex()
    version = subprocess.run([codex, "--version"], text=True, capture_output=True, check=False)
    print(f"Hixton Agent Swarm: {version.stdout.strip() or codex}")
    print("Authentication: normal ChatGPT/Codex login; no OpenAI API key is requested.")
    print("Real Binance orders are prohibited for this runner.")

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    branch_name = f"swarm/{safe_slug(args.mission)}-{run_id.lower()}"
    local_root = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "HixtonAgent"
    local_root.mkdir(parents=True, exist_ok=True)
    work = local_root / f"swarm-{safe_slug(args.mission)}-{uuid.uuid4().hex[:10]}"

    original_head = git(repo, "rev-parse", "HEAD")
    with mission_worktree(repo, branch_name, work):
        registry = validate_registry(work)
        mission = load_mission(work, args.mission)
        run_root = work / "agent_memory" / "swarm" / "runs" / str(mission["id"]) / run_id
        runtime = new_runtime(mission, run_id)
        runtime["base_commit"] = original_head
        runtime["mission_branch"] = branch_name
        write_json(run_root / "runtime.json", runtime)
        commit_all(work, f"docs(agent): start {mission['id']} swarm run {run_id}")

        completed = False
        for _ in range(args.max_rounds):
            round_no = int(runtime["round"])
            print(f"\n=== {mission['id']} / round {round_no} ===")
            _, reports = run_round(
                codex=codex,
                work=work,
                registry=registry,
                mission=mission,
                run_root=run_root,
                runtime=runtime,
                timeout_minutes=args.agent_timeout_minutes,
                retries=args.agent_retries,
            )
            completion = completion_from_reports(mission, reports)
            if completion.done:
                mark_done(runtime)
                write_json(run_root / "runtime.json", runtime)
                finalize_mission_in_taskboard(work, str(mission["id"]))
                commit_all(work, f"docs(agent): complete {mission['id']} swarm run {run_id}")
                completed = True
                break
            print(f"Round {round_no} reopened: {completion.reason}")
            reopen_round(runtime, reason=completion.reason)
            write_json(run_root / "runtime.json", runtime)
            commit_all(work, f"docs(agent): reopen {mission['id']} repair round")

        if not completed:
            runtime["state"] = "BLOCKED"
            runtime["updated_at_utc"] = utc_now_text()
            runtime.setdefault("history", []).append(
                {
                    "at_utc": utc_now_text(),
                    "event": "MAX_ROUNDS_EXHAUSTED",
                    "max_rounds": args.max_rounds,
                }
            )
            write_json(run_root / "runtime.json", runtime)
            commit_all(work, f"docs(agent): block {mission['id']} after max repair rounds")
            raise CommandError(
                f"Mission did not pass QA+governance within {args.max_rounds} rounds. "
                f"Evidence remains on local mission branch {branch_name}; it was NOT merged."
            )

        mission_head = git(work, "rev-parse", "HEAD")
        print(f"Mission gates PASS at {mission_head}.")

    # Mission worktree is now removed. Fast-forward only: any concurrent change to
    # the real branch prevents integration instead of being overwritten.
    if git(repo, "rev-parse", "HEAD") != original_head:
        raise CommandError("Main working branch moved during swarm run; refusing automatic integration")
    git(repo, "merge", "--ff-only", branch_name)
    if not args.no_push:
        git(repo, "push", "origin", branch)
    print(f"Mission {args.mission} merged to {branch} after QA_PASS + GOVERNANCE_PASS.")
    print("Dependent missions may now be NEW; rerun StartAgent.bat to continue them.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CommandError, SwarmContractError, json.JSONDecodeError) as exc:
        print(f"SWARM SAFETY STOP: {exc}", file=sys.stderr)
        raise SystemExit(2)

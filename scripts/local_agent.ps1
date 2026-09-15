param(
    [int]$MaxRounds = 8
)

$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Branch = 'agent/codex-supervisor-v1'
$AgentRoot = Join-Path $env:LOCALAPPDATA 'HixtonAgent'

function Require-Success([string]$What) {
    if ($LASTEXITCODE -ne 0) {
        throw "$What failed with exit code $LASTEXITCODE"
    }
}

function Read-State {
    $path = Join-Path $Repo 'agent_memory\state.json'
    if (-not (Test-Path $path)) { throw "Missing $path" }
    return Get-Content $path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Show-Progress($State) {
    Write-Host ''
    Write-Host ('Learning progress: {0}%' -f $State.progress_percent)
    Write-Host ('Current focus: {0}' -f $State.current_focus)
    foreach ($name in 'inventory','architecture','dataflows','ui_map','storage','tests','security','cross_check') {
        Write-Host ('  {0,-14} {1,3}%' -f $name, $State.areas.$name)
    }
    Write-Host ('Bootstrap complete: {0}' -f $State.bootstrap_complete)
    Write-Host ''
}

function Get-NpmCodex {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw 'npm was not found.'
    }
    $prefix = (& npm config get prefix).Trim()
    Require-Success 'npm config get prefix'
    $candidate = Join-Path $prefix 'codex.cmd'
    if (-not (Test-Path $candidate)) {
        throw "Current npm Codex launcher not found at $candidate. Run: npm install -g @openai/codex@latest"
    }
    return $candidate
}

Set-Location $Repo

$branchNow = (& git branch --show-current).Trim()
Require-Success 'git branch --show-current'
if ($branchNow -ne $Branch) {
    throw "Wrong branch: $branchNow. Switch to $Branch first."
}

$status = (& git status --porcelain) -join "`n"
Require-Success 'git status'
if ($status.Trim()) {
    throw "Working tree is not clean. Commit/stash local changes before starting the agent.`n$status"
}

Write-Host 'Updating local agent branch...'
& git pull --ff-only origin $Branch
Require-Success 'git pull'

$CodexPath = Get-NpmCodex
$version = (& $CodexPath --version 2>&1) -join ' '
Require-Success 'codex --version'
Write-Host "Hixton Codex CLI: $version"
Write-Host 'Authentication: normal ChatGPT/Codex login (no API key).'

New-Item -ItemType Directory -Force -Path $AgentRoot | Out-Null

for ($round = 1; $round -le $MaxRounds; $round++) {
    $state = Read-State
    Show-Progress $state
    if ($state.bootstrap_complete -eq $true) {
        Write-Host 'BOOTSTRAP COMPLETE. No engineering task was executed.'
        exit 0
    }

    $work = Join-Path $AgentRoot ('bootstrap-' + [guid]::NewGuid().ToString('N'))
    Write-Host "Starting learning round $round / $MaxRounds in disposable worktree..."

    try {
        & git worktree add --detach $work HEAD
        Require-Success 'git worktree add'

        $prompt = @"
Read AGENTS.md first and obey it exactly.
This is bootstrap learning round $round. The repository must be learned from its own source, tests, UI, DMS, configuration and workflows; do not rely on external explanations.
Read agent_memory/state.json and all relevant existing agent_memory files first. Continue from prior verified knowledge rather than restarting.
Use git ls-files as the completeness baseline. Inspect real implementations and trace calls in both directions. Prioritize the least-understood areas and unresolved_repository_questions.
During bootstrap this is LEARNING ONLY. You may modify only files under agent_memory/. Do not modify application code, UI, tests, configuration, workflows, DMS, strategy files, or runtime data. Never access or expose secrets and never send any real exchange order.
Update the required agent_memory documents and state.json with evidence-based percentages before finishing this round. Do not inflate progress. If a claim is uncertain, record it in unknowns.md instead of guessing.
Work thoroughly for this round and make meaningful progress before stopping.
"@

        & $CodexPath -c 'features.plugins=false' --ask-for-approval never --sandbox workspace-write --cd $work exec --ephemeral $prompt
        $codexExit = $LASTEXITCODE
        if ($codexExit -ne 0) {
            throw "Codex exited with code $codexExit. If your ChatGPT/Codex usage limit is reached, continue the repository work in ChatGPT/GitHub until the limit resets."
        }

        $tempMemory = Join-Path $work 'agent_memory'
        if (-not (Test-Path $tempMemory)) {
            throw 'Codex finished without an agent_memory directory.'
        }

        $realMemory = Join-Path $Repo 'agent_memory'
        New-Item -ItemType Directory -Force -Path $realMemory | Out-Null
        Get-ChildItem -Path $tempMemory -Force | ForEach-Object {
            Copy-Item $_.FullName -Destination $realMemory -Recurse -Force
        }
    }
    finally {
        Set-Location $Repo
        if (Test-Path $work) {
            & git worktree remove --force $work | Out-Null
            if ($LASTEXITCODE -ne 0) {
                & git worktree prune | Out-Null
                Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
            }
        }
    }

    $newState = Read-State
    Show-Progress $newState

    $outside = (& git status --porcelain --untracked-files=all | Where-Object { $_ -notmatch 'agent_memory[\\/]' }) -join "`n"
    if ($outside.Trim()) {
        throw "Safety stop: real repository has changes outside agent_memory/. Nothing will be committed.`n$outside"
    }

    & git add agent_memory
    Require-Success 'git add agent_memory'
    $staged = (& git diff --cached --name-only) -join "`n"
    if ($staged.Trim()) {
        $learningRound = [int]$newState.last_learning_round
        & git -c user.name='Hixton Local Agent' -c user.email='hixton-agent@local.invalid' commit -m "docs(agent): local repository learning round $learningRound"
        Require-Success 'git commit'
        & git push origin "HEAD:$Branch"
        Require-Success 'git push'
        Write-Host 'Persistent agent knowledge committed and pushed.'
    }
    else {
        Write-Host 'No persistent knowledge change was produced in this round.'
        break
    }
}

$finalState = Read-State
Show-Progress $finalState
if ($finalState.bootstrap_complete -eq $true) {
    Write-Host 'BOOTSTRAP COMPLETE.'
    exit 0
}

Write-Host "Bootstrap is still incomplete after $MaxRounds local rounds. Run StartAgent.bat again to continue."
exit 0

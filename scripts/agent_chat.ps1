$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Branch = 'agent/codex-supervisor-v1'
$AgentRoot = Join-Path $env:LOCALAPPDATA 'HixtonAgent'

function Require-Success([string]$What) {
    if ($LASTEXITCODE -ne 0) { throw "$What failed with exit code $LASTEXITCODE" }
}

function Read-State {
    $path = Join-Path $Repo 'agent_memory\state.json'
    if (-not (Test-Path $path)) { throw "Missing $path" }
    return Get-Content $path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Get-NpmCodex {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw 'npm was not found.' }
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
    throw "Working tree is not clean. Commit/stash local changes before starting AgentChat.`n$status"
}

Write-Host 'Updating local agent branch...'
& git pull --ff-only origin $Branch
Require-Success 'git pull'

$CodexPath = Get-NpmCodex
$version = (& $CodexPath --version 2>&1) -join ' '
Require-Success 'codex --version'
Write-Host "Hixton Codex CLI: $version"
Write-Host 'Authentication: normal ChatGPT/Codex login (no API key).'

$state = Read-State
Write-Host ('Agent learning progress: {0}%' -f $state.progress_percent)
Write-Host ('Bootstrap complete: {0}' -f $state.bootstrap_complete)
Write-Host ''
Write-Host 'You are entering an interactive chat with the persistent Hixton agent.'
Write-Host 'This chat uses your normal ChatGPT/Codex login and therefore the same Codex usage limit.'
Write-Host 'During bootstrap, AGENTS.md forbids production-code changes. The chat runs in a disposable worktree.'
Write-Host 'Only agent_memory changes can be copied back into the real repository when the chat ends.'
Write-Host ''

New-Item -ItemType Directory -Force -Path $AgentRoot | Out-Null
$work = Join-Path $AgentRoot ('chat-' + [guid]::NewGuid().ToString('N'))

try {
    & git worktree add --detach $work HEAD
    Require-Success 'git worktree add'

    $initialPrompt = @"
Read AGENTS.md and agent_memory/state.json before answering.
You are the persistent Hixton engineering agent in INTERACTIVE CHAT mode.
Use the verified knowledge in agent_memory as your durable memory and inspect repository source when needed instead of guessing.
If bootstrap_complete is false, remain in LEARNING-ONLY mode: you may answer questions, inspect and trace the repository, and improve agent_memory, but do not modify application code, UI, tests, DMS, configuration, workflows, strategy files, or runtime behavior.
Never read, print, copy, summarize, or expose credentials, API keys, secrets, ignored local files, or account data. Never send a real exchange order.
When the user asks about the bot, answer from verified repository evidence. If you do not yet know something, inspect it and update agent_memory rather than inventing an answer.
When useful, tell the user what you learned and what remains unresolved.
"@

    & $CodexPath --sandbox workspace-write --ask-for-approval on-request --cd $work $initialPrompt
    $chatExit = $LASTEXITCODE
    if ($chatExit -ne 0) {
        throw "Codex interactive chat exited with code $chatExit. If your Codex usage limit is reached, use ChatGPT/GitHub until it resets."
    }

    $tempMemory = Join-Path $work 'agent_memory'
    if (Test-Path $tempMemory) {
        $realMemory = Join-Path $Repo 'agent_memory'
        New-Item -ItemType Directory -Force -Path $realMemory | Out-Null
        Get-ChildItem -Path $tempMemory -Force | ForEach-Object {
            Copy-Item $_.FullName -Destination $realMemory -Recurse -Force
        }
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

$outside = (& git status --porcelain --untracked-files=all | Where-Object { $_ -notmatch 'agent_memory[\\/]' }) -join "`n"
if ($outside.Trim()) {
    throw "Safety stop: real repository has unexpected changes outside agent_memory/. Nothing will be committed.`n$outside"
}

& git add agent_memory
Require-Success 'git add agent_memory'
$staged = (& git diff --cached --name-only) -join "`n"
if ($staged.Trim()) {
    $newState = Read-State
    $round = [int]$newState.last_learning_round
    & git -c user.name='Hixton Local Agent' -c user.email='hixton-agent@local.invalid' commit -m "docs(agent): persist interactive learning round $round"
    Require-Success 'git commit'
    & git push origin "HEAD:$Branch"
    Require-Success 'git push'
    Write-Host 'Updated agent memory was committed and pushed.'
}
else {
    Write-Host 'No agent-memory changes to persist.'
}

$finalState = Read-State
Write-Host ('Agent learning progress now: {0}%' -f $finalState.progress_percent)
Write-Host ('Current focus: {0}' -f $finalState.current_focus)
Write-Host ('Bootstrap complete: {0}' -f $finalState.bootstrap_complete)

<#
.SYNOPSIS
    Ralph Wiggum Loop - Dash Migration variant.

.DESCRIPTION
    Outer loop for iterative Dash frontend development (Reflex -> Dash migration).
    Each iteration spawns a fresh `claude --print` invocation.
    Memory persists via filesystem only: git commits, progress.txt, IMPLEMENTATION_PLAN.md, guardrails.md.

    Runs until completion (<promise>COMPLETE</promise>) or circuit breaker trips.
    No arbitrary iteration limit — the loop continues until done.

    Circuit breakers prevent runaway costs:
    - No git changes for N consecutive iterations (stalled)
    - Same error repeated N consecutive iterations (stuck)

.PARAMETER Model
    Claude model to use. Default: "opus".

.PARAMETER BranchName
    Optional git branch name. If provided, creates/checks out the branch before starting.

.PARAMETER MaxNoProgress
    Number of consecutive iterations with no git changes before circuit breaker trips. Default: 3.

.PARAMETER MaxSameError
    Number of consecutive iterations with the same error before circuit breaker trips. Default: 3.

.EXAMPLE
    .\ralph.ps1 -Model "opus" -BranchName "feature/dash-migration"

.EXAMPLE
    .\ralph.ps1 -Model "sonnet" -MaxNoProgress 2
#>

param(
    [string]$Model = "opus",
    [string]$BranchName,
    [int]$MaxNoProgress = 3,
    [int]$MaxSameError = 3
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$promptFile = Join-Path $scriptDir "RALPH_PROMPT.md"
$planFile = Join-Path $scriptDir "IMPLEMENTATION_PLAN.md"
$guardrailsFile = Join-Path $scriptDir "guardrails.md"
$progressFile = Join-Path $scriptDir "progress.txt"
$logDir = Join-Path $scriptDir "logs"

# --- Validation ---

if (-not (Test-Path $promptFile)) {
    Write-Error "RALPH_PROMPT.md not found at $promptFile"
    exit 1
}

if (-not (Test-Path $planFile)) {
    Write-Error "IMPLEMENTATION_PLAN.md not found at $planFile"
    exit 1
}

if (-not (Test-Path $guardrailsFile)) {
    Write-Warning "guardrails.md not found at $guardrailsFile - loop may miss known failure patterns"
}

# Ensure progress.txt exists
if (-not (Test-Path $progressFile)) {
    @"
# Progress Log

## Design Context
<!-- Design decisions and context go here -->

## Reflex Patterns
<!-- Reusable Reflex patterns discovered during development -->

## Iteration Log
<!-- Each iteration appends a structured entry below. See RALPH_PROMPT.md for format. -->
"@ | Set-Content -Path $progressFile -Encoding UTF8
    Write-Host "Created progress.txt"
}

# Ensure logs directory exists
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
    Write-Host "Created logs directory"
}

# --- Git Setup ---

$gitInitialised = $false
try {
    $result = git rev-parse --is-inside-work-tree 2>&1
    if ($LASTEXITCODE -eq 0 -and $result -eq "true") {
        $gitInitialised = $true
    }
} catch {
    # Not a git repo — expected on first run
}

if (-not $gitInitialised) {
    Write-Host "Initialising git repository..."
    git init
    git add -A
    git commit -m "Initial commit before Ralph loop"
}

if ($BranchName) {
    $currentBranch = git branch --show-current
    if ($currentBranch -ne $BranchName) {
        $branchExists = git branch --list $BranchName
        if ($branchExists) {
            Write-Host "Switching to existing branch: $BranchName"
            git checkout $BranchName
        } else {
            Write-Host "Creating branch: $BranchName"
            git checkout -b $BranchName
        }
    }
}

# --- Circuit Breaker State ---

$noProgressCount = 0
$lastErrorSignature = ""
$sameErrorCount = 0

# Capture the HEAD commit hash before the loop starts
$preLoopHead = git rev-parse HEAD 2>$null

# --- Main Loop ---

$promptContent = Get-Content -Path $promptFile -Raw

# Count existing iterations from progress.txt to track total across runs
$existingIterations = 0
if (Test-Path $progressFile) {
    $existingIterations = (Select-String -Path $progressFile -Pattern "## Iteration" -AllMatches | Measure-Object).Count
}

Write-Host ""
Write-Host "===== Ralph Wiggum Loop (Dash Migration) =====" -ForegroundColor Cyan
Write-Host "Model: $Model | Runs until COMPLETE" -ForegroundColor Cyan
Write-Host "Circuit breakers: no-progress=$MaxNoProgress, same-error=$MaxSameError" -ForegroundColor Cyan
if ($BranchName) { Write-Host "Branch: $BranchName" -ForegroundColor Cyan }
if ($existingIterations -gt 0) { Write-Host "Previous iterations: $existingIterations" -ForegroundColor Cyan }
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host ""

$i = 0
while ($true) {
    $i++
    $totalIteration = $existingIterations + $i
    Write-Host ""
    Write-Host "--- Iteration $i (Total: $totalIteration) ---" -ForegroundColor Yellow

    # Record HEAD before this iteration
    $headBefore = git rev-parse HEAD 2>$null

    # Show start time and status
    $iterStart = Get-Date
    Write-Host "  Started: $($iterStart.ToString('HH:mm:ss'))" -ForegroundColor DarkGray
    Write-Host "  Spawning Claude ($Model)..." -ForegroundColor DarkGray
    Write-Host ""

    # Spawn fresh Claude instance with stream-json for tool call visibility
    $logFile = Join-Path $logDir "iteration_$totalIteration.log"
    $rawLogFile = Join-Path $logDir "iteration_$totalIteration.raw.jsonl"
    $maxRetries = 10
    $retryCount = 0
    $outputString = ""
    $apiOverloaded = $false

    do {
        $apiOverloaded = $false
        $textBuilder = [System.Text.StringBuilder]::new()
        $toolCount = 0

        # Clear raw log file for this attempt
        if (Test-Path $rawLogFile) { Remove-Item $rawLogFile -Force }

        if ($retryCount -gt 0) {
            $backoffSeconds = [Math]::Pow(2, $retryCount - 1)
            Write-Host "  [Retry $retryCount/$maxRetries] API overloaded, waiting $backoffSeconds seconds..." -ForegroundColor DarkYellow
            Start-Sleep -Seconds $backoffSeconds
            Write-Host "  Retrying Claude invocation..." -ForegroundColor DarkGray
        }

        $promptContent | claude --print --verbose --dangerously-skip-permissions --model $Model --output-format stream-json 2>&1 | ForEach-Object {
            $line = $_.ToString().Trim()
            if (-not $line) { return }

            # Save raw event for debugging (with error handling for stream closure)
            try {
                Add-Content -Path $rawLogFile -Value $line -Encoding UTF8 -ErrorAction SilentlyContinue
            } catch {
                # Stream closed or file locked - ignore and continue
            }

            try {
                $evt = $line | ConvertFrom-Json -ErrorAction Stop

                # --- Tool use start (show tool name) ---
                if ($evt.type -eq 'content_block_start' -and $evt.content_block.type -eq 'tool_use') {
                    $toolCount++
                    $toolName = $evt.content_block.name
                    Write-Host "  [$toolName]" -ForegroundColor DarkCyan
                }
                # --- Assistant text content (streaming deltas) ---
                elseif ($evt.type -eq 'content_block_delta' -and $evt.delta.type -eq 'text_delta' -and $evt.delta.text) {
                    Write-Host -NoNewline $evt.delta.text
                    [void]$textBuilder.Append($evt.delta.text)
                }
                # --- Result event (error display + text capture for circuit breakers) ---
                elseif ($evt.type -eq 'result') {
                    if ($evt.subtype -eq 'error_result' -and $evt.error) {
                        Write-Host "  [ERROR] $($evt.error)" -ForegroundColor Red
                        [void]$textBuilder.AppendLine("ERROR: $($evt.error)")
                    }
                    elseif ($evt.result) {
                        # Capture for circuit breaker detection; don't print
                        # (text already displayed via streaming deltas above)
                        [void]$textBuilder.AppendLine($evt.result)
                    }
                }
                # --- Message-level content (final message summary) ---
                elseif ($evt.message -and $evt.message.content) {
                    foreach ($block in $evt.message.content) {
                        if ($block.type -eq 'text' -and $block.text) {
                            Write-Host $block.text
                            [void]$textBuilder.AppendLine($block.text)
                        }
                        elseif ($block.type -eq 'tool_use') {
                            $toolCount++
                            Write-Host "  [$($block.name)]" -ForegroundColor DarkCyan
                        }
                        # Silently ignore tool_result and other block types
                    }
                }
                # All other JSON events (input_json_delta, content_block_stop,
                # message_start, message_stop, ping, etc.) are silently ignored

            } catch {
                # Not valid JSON — only print if it looks like meaningful stderr
                # (filter out JSON fragments from multi-line events)
                if ($line -and $line -notmatch '^\s*[\{\[\}\]"]') {
                    Write-Host $line -ForegroundColor DarkYellow
                    [void]$textBuilder.AppendLine($line)
                }
            }
        }

        $outputString = $textBuilder.ToString()

        # Check for 529 overloaded error
        if ($outputString -match "529.*overloaded|overloaded_error") {
            $apiOverloaded = $true
            $retryCount++
            if ($retryCount -ge $maxRetries) {
                Write-Host "  [ERROR] API overloaded after $maxRetries retries, giving up." -ForegroundColor Red
            }
        }
    } while ($apiOverloaded -and $retryCount -lt $maxRetries)

    $outputString | Set-Content -Path $logFile -Encoding UTF8

    # Show elapsed time and tool count
    $elapsed = (Get-Date) - $iterStart
    Write-Host ""
    Write-Host "  Finished: $(Get-Date -Format 'HH:mm:ss') (elapsed: $($elapsed.ToString('mm\:ss')), tools: $toolCount)" -ForegroundColor DarkGray

    # --- Circuit Breaker: No Progress ---
    $headAfter = git rev-parse HEAD 2>$null
    if ($headAfter -eq $headBefore) {
        $noProgressCount++
        Write-Host "  [Circuit Breaker] No git commits this iteration ($noProgressCount/$MaxNoProgress)" -ForegroundColor DarkYellow
        if ($noProgressCount -ge $MaxNoProgress) {
            Write-Host ""
            Write-Host "===== CIRCUIT BREAKER: NO PROGRESS =====" -ForegroundColor Red
            Write-Host "No git commits for $MaxNoProgress consecutive iterations. The loop is stalled." -ForegroundColor Red
            Write-Host "Check progress.txt and logs/ for details on what went wrong." -ForegroundColor Red
            exit 1
        }
    } else {
        $noProgressCount = 0
    }

    # --- Circuit Breaker: Repeated Error ---
    $errorLines = $outputString | Select-String -Pattern "(?i)(error|exception|failed|fatal)[:.].*" -AllMatches
    if ($errorLines) {
        $filteredErrors = $errorLines.Matches | Where-Object { $_.Value -notmatch "529|overloaded" } | Select-Object -First 3
        $currentErrorSignature = ($filteredErrors | ForEach-Object { $_.Value }) -join "|"
        if ($currentErrorSignature -and $currentErrorSignature -eq $lastErrorSignature) {
            $sameErrorCount++
            Write-Host "  [Circuit Breaker] Same error pattern repeated ($sameErrorCount/$MaxSameError)" -ForegroundColor DarkYellow
            if ($sameErrorCount -ge $MaxSameError) {
                Write-Host ""
                Write-Host "===== CIRCUIT BREAKER: REPEATED ERROR =====" -ForegroundColor Red
                Write-Host "Same error pattern for $MaxSameError consecutive iterations:" -ForegroundColor Red
                Write-Host "  $currentErrorSignature" -ForegroundColor Red
                Write-Host "Check progress.txt and logs/ for details." -ForegroundColor Red
                exit 1
            }
        } elseif ($currentErrorSignature) {
            $sameErrorCount = 0
        }
        $lastErrorSignature = $currentErrorSignature
    } else {
        $sameErrorCount = 0
        $lastErrorSignature = ""
    }

    # --- Push to Remote ---
    $hasRemote = git remote 2>$null
    if ($hasRemote) {
        $currentBranch = git branch --show-current
        git push origin $currentBranch 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  Pushed to remote." -ForegroundColor Green
        } else {
            Write-Host "  Push failed or no remote configured - continuing." -ForegroundColor DarkYellow
        }
    }

    # --- Check for Completion ---
    if ($outputString -match "<promise>COMPLETE</promise>") {
        Write-Host ""
        Write-Host "===== COMPLETE =====" -ForegroundColor Green
        Write-Host "Dash migration finished after $i iteration(s) this run ($totalIteration total)." -ForegroundColor Green
        exit 0
    }

    # Brief pause between iterations
    Start-Sleep -Seconds 2
}

# ---------------------------------------------------------------------------
# One-click publish: bump version -> commit -> push -> tag -> GitHub builds.
#   Double-click publish.bat, or run this file directly.
#   Automation: MICMUTE_VERSION / MICMUTE_YES / MICMUTE_REMOTE
# ---------------------------------------------------------------------------
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$script:Changed = $false
$script:VersionBumped = $false
$script:Committed = $false

function GitRun([string[]]$a) {
    $errFile = [IO.Path]::GetTempFileName()
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $out = & git @a 2> $errFile
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    $err = ""
    if (Test-Path $errFile) {
        $err = (Get-Content $errFile -Raw)
        Remove-Item $errFile -Force -ErrorAction SilentlyContinue
    }
    $text = (@($out) | Out-String).Trim()
    if ($err) { $text = ($text + "`n" + $err).Trim() }
    [pscustomobject]@{ Out = $text; Code = $code }
}

function Say($text, $color = "Gray") { Write-Host $text -ForegroundColor $color }

# strip PowerShell's native-command error wrapping so the user sees real git text
function CleanGitOut($text) {
    if (-not $text) { return "" }
    $lines = $text -split "`r?`n" | Where-Object {
        $_ -notmatch 'NativeCommandError|CategoryInfo|FullyQualifiedErrorId' -and
        $_ -notmatch '^\s*\+ ' -and
        $_ -notmatch '^At .*(publish\.ps1|line:)'
    }
    return (($lines -join "`n").Trim())
}

function Fail($message, $detail) {
    Write-Host ""
    Say "  FAILED: $message" "Red"
    if ($detail) {
        Write-Host ""
        Say "  --- git output ---" "DarkYellow"
        Write-Host (CleanGitOut $detail) -ForegroundColor DarkYellow
    }
    Write-Host ""
    Say "  Nothing was published. Common causes:" "Yellow"
    Say "    * GitHub asked for a login and the browser window was closed/cancelled" "Yellow"
    Say "    * the repo was created by uploading files, so histories differ (this script" "Yellow"
    Say "      now offers to rebase automatically - answer y)" "Yellow"
    Say "    * the token/app password expired: run  git credential-manager configure" "Yellow"
    Say "    * you are not a collaborator on the repository" "Yellow"
    Say "    * GitHub sign-in: run  git credential-manager configure  once" "Yellow"
    Say ("  full log: " + (Join-Path $env:TEMP "michud-publish.log")) "DarkGray"
    Write-Host ""
    throw $message
}

Say ""
Say "  MIC MUTE  ·  PUBLISH" "Black"
Say ""

$logPath = Join-Path $env:TEMP "michud-publish.log"
try { Start-Transcript -Path $logPath -Force | Out-Null } catch { }

try {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Fail "Git is not installed or not on PATH." "Install Git for Windows, then run this again."
    }
    Say ("  git    : " + (GitRun @("--version")).Out)

    # ---------------- version -------------------------------------------
    $mainFile = Join-Path $root "main.py"
    $text = [IO.File]::ReadAllText($mainFile)
    if ($text -notmatch 'APP_VERSION = "([0-9]+\.[0-9]+\.[0-9]+)"') {
        Fail "Could not find APP_VERSION in main.py." ""
    }
    $current = $Matches[1]
    $bits = $current.Split('.')
    $suggest = "{0}.{1}.{2}" -f $bits[0], $bits[1], ([int]$bits[2] + 1)
    Say "  version: v$current"

    # ---------------- repository + remote --------------------------------
    if (-not (Test-Path (Join-Path $root ".git"))) {
        GitRun @("init") | Out-Null
        Say "  Initialised a new git repository."
    }

    if ([string]::IsNullOrWhiteSpace((GitRun @("remote")).Out)) {
        $default = "https://github.com/Lightoo00/Mic-Mute-for-Voicemeeter-Windows.git"
        $url = $env:MICMUTE_REMOTE
        if ([string]::IsNullOrWhiteSpace($url)) {
            $url = Read-Host "  GitHub repo URL (Enter = $default)"
        }
        if ([string]::IsNullOrWhiteSpace($url)) { $url = $default }
        GitRun @("remote", "add", "origin", $url) | Out-Null
        Say "  remote : $url"
    }
    $remoteUrl = (GitRun @("remote", "get-url", "origin")).Out
    if ($remoteUrl -notmatch 'github\.com') {
        Say "  note   : remote is not GitHub ($remoteUrl)" "Yellow"
    }

    $hasHead = (GitRun @("rev-parse", "--verify", "HEAD")).Code -eq 0
    if (-not $hasHead) {
        GitRun @("checkout", "-B", "main") | Out-Null
        $branch = "main"
    } else {
        $branch = (GitRun @("rev-parse", "--abbrev-ref", "HEAD")).Out
        if ([string]::IsNullOrWhiteSpace($branch) -or $branch -eq "HEAD") {
            GitRun @("checkout", "-B", "main") | Out-Null
            $branch = "main"
        }
    }

    # ---------------- commit identity ------------------------------------
    if ([string]::IsNullOrWhiteSpace((GitRun @("config", "user.name")).Out)) {
        $who = "Mic Mute Releaser"
        if ($remoteUrl -match 'github\.com[:/]([^/]+)/') { $who = $Matches[1] }
        GitRun @("config", "user.name", $who) | Out-Null
    }
    if ([string]::IsNullOrWhiteSpace((GitRun @("config", "user.email")).Out)) {
        $who = "michud"
        if ($remoteUrl -match 'github\.com[:/]([^/]+)/') { $who = $Matches[1] }
        GitRun @("config", "user.email", "$who@users.noreply.github.com") | Out-Null
    }

    # ---------------- sync with the remote BEFORE touching version ------
    Say "  fetching origin ..."
    $fetch = GitRun @("fetch", "--quiet", "origin")
    if ($fetch.Code -ne 0) {
        Fail "Could not reach the GitHub repository (network, login or permissions)." $fetch.Out
    }

    $remoteRef = "origin/$branch"
    $remoteExists = (GitRun @("rev-parse", "--verify", $remoteRef)).Code -eq 0
    if ($remoteExists) {
        $baseCode = (GitRun @("merge-base", "HEAD", $remoteRef)).Code
        if ($baseCode -ne 0) {
            Say "  The remote history is unrelated to this folder." "Yellow"
            Say "  (the repository was probably created by uploading files on github.com)" "Yellow"
            if ($env:MICMUTE_YES -eq "1") { $sync = "y" }
            else { $sync = Read-Host "  Rebase these files on top of $remoteRef? (y/N)" }
            if ($sync -notmatch '^(y|Y)') {
                Fail "Cancelled: local and remote histories are unrelated." ""
            }
            $backup = "backup-local-" + (Get-Date -Format "yyyyMMdd-HHmmss")
            GitRun @("branch", $backup) | Out-Null
            $reset = GitRun @("reset", "--mixed", $remoteRef)
            if ($reset.Code -ne 0) { Fail "Could not rebase on $remoteRef." $reset.Out }
            Say "  synced : files kept, history now follows $remoteRef (backup: $backup)" "Green"
        } else {
            $behind = [int](GitRun @("rev-list", "--count", "HEAD..$remoteRef")).Out
            if ($behind -gt 0) {
                Say "  pulling $behind commit(s) from $remoteRef ..."
                $pull = GitRun @("pull", "--rebase", "origin", $branch)
                if ($pull.Code -ne 0) {
                    Fail "Could not rebase onto the remote branch. Resolve it manually, then retry." $pull.Out
                }
            }
        }
    }

    # ---------------- version bump ---------------------------------------
    $answer = $env:MICMUTE_VERSION
    if ([string]::IsNullOrWhiteSpace($answer)) {
        $answer = Read-Host "  new version (Enter = v$suggest)"
    }
    if ([string]::IsNullOrWhiteSpace($answer)) { $answer = $suggest }
    $new = $answer.Trim().TrimStart('v', 'V')
    if ($new -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$') { Fail "Invalid version: $answer" "" }

    if ($new -ne $current) {
        $text = $text -replace 'APP_VERSION = "[0-9]+\.[0-9]+\.[0-9]+"', "APP_VERSION = `"$new`""
        [IO.File]::WriteAllText($mainFile, $text, (New-Object Text.UTF8Encoding $false))
        $batFile = Join-Path $root "build-windows.bat"
        if (Test-Path $batFile) {
            $bat = [IO.File]::ReadAllText($batFile)
            $bat = $bat -replace 'Mic-Mute-Windows-v[0-9]+\.[0-9]+\.[0-9]+\.zip', "Mic-Mute-Windows-v$new.zip"
            [IO.File]::WriteAllText($batFile, $bat, (New-Object Text.UTF8Encoding $false))
        }
        $script:VersionBumped = $true
        Say "  bumped : v$current -> v$new" "Green"
    }

    # ---------------- commit + push --------------------------------------
    $before = (GitRun @("rev-parse", "--verify", "HEAD")).Out
    if ((GitRun @("rev-parse", "--verify", "HEAD")).Code -ne 0) { $before = "" }
    GitRun @("add", "-A") | Out-Null
    $pending = (GitRun @("status", "--porcelain")).Out
    if ([string]::IsNullOrWhiteSpace($pending)) {
        Say "  no file changes - publishing the tag only" "Yellow"
    } else {
        $count = ($pending -split "`n").Count
        $commit = GitRun @("commit", "-m", "release v$new")
        if ($commit.Code -ne 0) { Fail "git commit failed." $commit.Out }
        $script:Committed = $true
        Say "  committed $count file(s)" "Green"
    }

    Say "  pushing $branch ..."
    $push = GitRun @("push", "-u", "origin", $branch)
    if ($push.Code -ne 0) {
        if ($push.Out -match "rejected|non-fast-forward") {
            Say "  remote moved ahead - rebasing and retrying ..." "Yellow"
            $pull = GitRun @("pull", "--rebase", "origin", $branch)
            if ($pull.Code -eq 0) { $push = GitRun @("push", "-u", "origin", $branch) }
        }
        if ($push.Code -ne 0) {
            # undo the local commit and version bump so a retry stays clean
            if ($script:Committed) {
                if ($before) { GitRun @("reset", "--soft", $before) | Out-Null }
                else { GitRun @("update-ref", "-d", "HEAD") | Out-Null }
            }
            if ($script:VersionBumped) {
                $now = [IO.File]::ReadAllText($mainFile)
                $now = $now -replace 'APP_VERSION = "[0-9]+\.[0-9]+\.[0-9]+"', "APP_VERSION = `"$current`""
                [IO.File]::WriteAllText($mainFile, $now, (New-Object Text.UTF8Encoding $false))
                $batFile = Join-Path $root "build-windows.bat"
                if (Test-Path $batFile) {
                    $bat = [IO.File]::ReadAllText($batFile)
                    $bat = $bat -replace 'Mic-Mute-Windows-v[0-9]+\.[0-9]+\.[0-9]+\.zip', "Mic-Mute-Windows-v$current.zip"
                    [IO.File]::WriteAllText($batFile, $bat, (New-Object Text.UTF8Encoding $false))
                }
                Say "  rolled back to v$current (nothing was published)" "Yellow"
            }
            Fail "git push was rejected by GitHub." $push.Out
        }
    }
    Say "  pushed $branch" "Green"

    # ---------------- tag ------------------------------------------------
    $tag = "v$new"
    if ((GitRun @("tag", "--list", $tag)).Out) {
        if ($env:MICMUTE_YES -eq "1") { $move = "y" }
        else { $move = Read-Host "  tag $tag already exists - move it here? (y/N)" }
        if ($move -match '^(y|Y)') {
            GitRun @("tag", "-d", $tag) | Out-Null
            GitRun @("push", "origin", ":refs/tags/$tag") | Out-Null
        } else {
            Fail "Tag $tag already exists. Choose a higher version number." ""
        }
    }
    # sign the tag when a signing key is configured (github shows "Verified")
    $signKey = (GitRun @("config", "user.signingkey")).Out
    if ($signKey) {
        $tagResult = GitRun @("tag", "-s", $tag, "-m", "release $tag")
        if ($tagResult.Code -ne 0) {
            Say "  signing failed - creating an unsigned tag instead" "Yellow"
            GitRun @("tag", "-d", $tag) | Out-Null
            $tagResult = GitRun @("tag", "-a", $tag, "-m", "release $tag")
        } else {
            Say "  tag signed with your key (will show Verified on GitHub)" "Green"
        }
    } else {
        $tagResult = GitRun @("tag", "-a", $tag, "-m", "release $tag")
    }
    if ($tagResult.Code -ne 0) { Fail "Could not create tag $tag." $tagResult.Out }
    $tagPush = GitRun @("push", "origin", $tag)
    if ($tagPush.Code -ne 0) { Fail "Pushing the tag failed." $tagPush.Out }

    Say ""
    Say "  Published v$new - GitHub Actions is building it now." "Green"

    # ---------------- wait until the release is really live --------------
    if ($remoteUrl -match 'github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$') {
        $owner = $Matches[1]
        $name = $Matches[2]
        $api = "https://api.github.com/repos/$owner/$name/releases/tags/$tag"
        Say "  build log : https://github.com/$owner/$name/actions" "Cyan"
        Say "  releases  : https://github.com/$owner/$name/releases" "Cyan"
        Say "  waiting for the EXE (about 2-4 minutes) ..."
        $live = $false
        for ($i = 0; $i -lt 40; $i++) {
            Start-Sleep -Seconds 8
            try {
                $release = Invoke-RestMethod -Uri $api -Headers @{ "User-Agent" = "michud-publish" } -TimeoutSec 15
                $asset = $release.assets | Where-Object { $_.name -like "*.zip" } | Select-Object -First 1
                if ($asset) {
                    $live = $true
                    Say ("  update is LIVE: " + $asset.name + " (" + [int]($asset.size / 1MB) + " MB)") "Green"
                    break
                }
            } catch { }
        }
        if (-not $live) {
            Say "  still building - open the Actions page above and refresh in a minute." "Yellow"
        } else {
            Say "  installed copies will pick it up automatically on their next launch." "Gray"
        }
    }
    Say ""
}
catch {
    if ($_.Exception.Message -and $_.Exception.Message -notmatch "^Aborted|^Cancelled") {
        # Fail() already printed everything for its own errors
    }
    exit 1
}
finally {
    try { Stop-Transcript | Out-Null } catch { }
}

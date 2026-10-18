# Downloads outlook-mcp-rs.exe (the Outlook MCP server) from the GitHub releases of
# https://github.com/adamkopelman/outlook-mcp-rs into this folder and verifies its SHA-256.
# Safe to re-run: an existing outlook-mcp-rs.exe is left alone (it may be your own build) unless -Force.
#
#   powershell -ExecutionPolicy Bypass -File vendor\outlook-mcp-rs\download-outlook-mcp-rs.ps1 [-Force] [-SetUserEnv]
#
# -SetUserEnv also sets the user environment variable OUTLOOK_MCP_BIN to the exe's full path (what
# .mcp.json and opencode.json launch); restart your terminal/harness afterwards.
# Works in Windows PowerShell 5.1 and PowerShell 7+. Keep the version and hash in sync with
# .claude/skills/gtd-setup/apply.py and download-outlook-mcp-rs.sh.
param([switch]$Force, [switch]$SetUserEnv)
$ErrorActionPreference = 'Stop'

$Version = 'v0.3.0'
$Url     = "https://github.com/adamkopelman/outlook-mcp-rs/releases/download/$Version/outlook-mcp-rs.exe"
$Sha256  = 'b033325029562cac858551052ce6870010ecf8c9325206cf0233f45212619048'
$Dest    = Join-Path $PSScriptRoot 'outlook-mcp-rs.exe'
$Part    = "$Dest.part"

if ((Test-Path -LiteralPath $Dest) -and -not $Force) {
    Write-Host "OK: $Dest is already present (left as is; -Force downloads $Version over it)."
} else {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    $ProgressPreference = 'SilentlyContinue'   # the progress bar makes Invoke-WebRequest very slow in 5.1
    Write-Host "Downloading outlook-mcp-rs $Version from $Url ..."
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $Part
    } catch {
        if (Test-Path -LiteralPath $Part) { Remove-Item -LiteralPath $Part -Force }
        throw "Could not download $Url ($($_.Exception.Message)). Are you offline? Nothing was installed; re-run this script when you're connected."
    }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Part).Hash.ToLowerInvariant()
    if ($actual -ne $Sha256) {
        Remove-Item -LiteralPath $Part -Force
        throw "Checksum mismatch for outlook-mcp-rs.exe: expected $Sha256, got $actual. Nothing was installed."
    }
    Move-Item -LiteralPath $Part -Destination $Dest -Force
    Write-Host "OK: saved and verified $Dest"
}

$full = (Resolve-Path -LiteralPath $Dest).Path
if ($SetUserEnv) {
    [Environment]::SetEnvironmentVariable('OUTLOOK_MCP_BIN', $full, 'User')
    Write-Host "Set user environment variable OUTLOOK_MCP_BIN=$full (restart your terminal/harness)."
} elseif ($env:OUTLOOK_MCP_BIN -ne $full) {
    Write-Host "To let .mcp.json / opencode.json launch it, set OUTLOOK_MCP_BIN (or re-run with -SetUserEnv):"
    Write-Host "  setx OUTLOOK_MCP_BIN `"$full`""
}

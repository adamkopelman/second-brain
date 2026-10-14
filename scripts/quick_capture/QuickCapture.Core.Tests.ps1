# Tests for QuickCapture.Core.ps1 — plain asserts, no Pester needed.
#   powershell -ExecutionPolicy Bypass -File scripts\quick_capture\QuickCapture.Core.Tests.ps1
# (also runs under pwsh on macOS/Linux). Exits 1 on any failure.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'QuickCapture.Core.ps1')

$script:failed = 0
function Check([string]$Name, $Actual, $Expected) {
    if ("$Actual" -ceq "$Expected") { Write-Host "ok   $Name" }
    else { Write-Host "FAIL $Name`n     expected: $Expected`n     actual:   $Actual"; $script:failed++ }
}

$wed = Get-Date -Year 2026 -Month 10 -Day 14  # a Wednesday

# --- dates
Check 'today'         (Resolve-QcDate 'today' $wed).ToString('yyyy-MM-dd') '2026-10-14'
Check 'tmr'           (Resolve-QcDate 'tmr' $wed).ToString('yyyy-MM-dd') '2026-10-15'
Check 'fri'           (Resolve-QcDate 'fri' $wed).ToString('yyyy-MM-dd') '2026-10-16'
Check 'wed = next wed' (Resolve-QcDate 'wednesday' $wed).ToString('yyyy-MM-dd') '2026-10-21'
Check '+3'            (Resolve-QcDate '+3' $wed).ToString('yyyy-MM-dd') '2026-10-17'
Check 'next-week'     (Resolve-QcDate 'next-week' $wed).ToString('yyyy-MM-dd') '2026-10-19'
Check 'iso'           (Resolve-QcDate '2026-12-01' $wed).ToString('yyyy-MM-dd') '2026-12-01'
Check 'm/d past -> next year' (Resolve-QcDate '1/5' $wed).ToString('yyyy-MM-dd') '2027-01-05'
Check 'm-d'           (Resolve-QcDate '10-20' $wed).ToString('yyyy-MM-dd') '2026-10-20'
Check 'junk'          ($null -eq (Resolve-QcDate 'blah' $wed)) 'True'
Check 'bad iso'       ($null -eq (Resolve-QcDate '2026-02-31' $wed)) 'True'
Check 'bad m/d'       ($null -eq (Resolve-QcDate '2/30' $wed)) 'True'

# --- parsing
$p = ConvertFrom-QcText 'Call the dentist #phone !fri ^2026-10-31' -Today $wed
Check 'line'  $p.Line '- [ ] Call the dentist #phone [scheduled:: 2026-10-16] [due:: 2026-10-31]'
Check 'title' $p.Title 'Call the dentist'
Check 'plain inbox' (ConvertFrom-QcText 'Buy milk' -Today $wed).Line '- [ ] Buy milk'
Check 'today mode' (ConvertFrom-QcText 'Send invoice' -Mode today -Today $wed).Line `
    '- [ ] Send invoice #next #anywhere [scheduled:: 2026-10-14]'
Check 'today keeps context + !when' (ConvertFrom-QcText 'Pay rent #computer !tmr' -Mode today -Today $wed).Line `
    '- [ ] Pay rent #computer #next [scheduled:: 2026-10-15]'
Check 'waiting gets since' (ConvertFrom-QcText 'Figures from Sam #waiting' -Today $wed).Line `
    '- [ ] Figures from Sam #waiting [since:: 2026-10-14]'
$bad = ConvertFrom-QcText 'Thing !someday-ish' -Today $wed
Check 'unknown date stays in title' $bad.Title 'Thing !someday-ish'
Check 'unknown date reported' $bad.Errors.Count 1
Check 'hebrew' (ConvertFrom-QcText 'להתקשר לרופא #phone' -Today $wed).Line '- [ ] להתקשר לרופא #phone'
Check 'preview' (Format-QcPreview (ConvertFrom-QcText 'x #phone !fri' -Today $wed)) 'Inbox  ·  When Fri Oct 16  ·  #phone'

# --- slugs
Check 'slug'        (ConvertTo-QcSlug 'Call the dentist!') 'call-the-dentist'
Check 'slug hebrew' (ConvertTo-QcSlug 'להתקשר לרופא') 'להתקשר-לרופא'
Check 'slug empty'  (ConvertTo-QcSlug '!!!') 'item'
Check 'slug long'   ((ConvertTo-QcSlug ('a b ' * 30)).Length -le 40) 'True'

# --- files
$vault = Join-Path ([System.IO.Path]::GetTempPath()) ("qc-test-" + [guid]::NewGuid())
New-Item -ItemType Directory $vault | Out-Null
try {
    $rel = New-QcCapture -Vault $vault -Text 'Call the dentist #phone' -Today $wed
    Check 'file name' $rel '00 Inbox/2026-10-14 call-the-dentist.md'
    $bytes = [System.IO.File]::ReadAllBytes((Join-Path $vault $rel))
    Check 'no BOM' ($bytes[0] -ne 0xEF) 'True'
    Check 'content' ([System.IO.File]::ReadAllText((Join-Path $vault $rel))) `
        "---`ntype: inbox`ncaptured: 2026-10-14`n---`n- [ ] Call the dentist #phone`n"
    $rel2 = New-QcCapture -Vault $vault -Text 'Call the dentist' -Today $wed
    Check 'no overwrite' $rel2 '00 Inbox/2026-10-14 call-the-dentist-2.md'
    $rel3 = New-QcCapture -Vault $vault -Text "https://example.com/article`r`nworth reading" -Note -Today $wed
    Check 'note name' $rel3 '00 Inbox/2026-10-14 example-com-article.md'
    Check 'note body' ([System.IO.File]::ReadAllText((Join-Path $vault $rel3))) `
        "---`ntype: inbox`ncaptured: 2026-10-14`n---`nhttps://example.com/article`nworth reading`n"
    $threw = $false; try { New-QcCapture -Vault $vault -Text '  #phone !fri ' -Today $wed | Out-Null } catch { $threw = $true }
    Check 'tags only -> refused' $threw 'True'
} finally {
    Remove-Item -Recurse -Force $vault
}

# --- config + hotkeys
$cfgPath = Join-Path ([System.IO.Path]::GetTempPath()) ("qc-cfg-" + [guid]::NewGuid() + '.json')
'{ "hotkeys": { "quick_add": "Ctrl+Shift+Space" }, "notify": false, "_comment": "x" }' | Set-Content $cfgPath
try {
    $cfg = Get-QcConfig $cfgPath
    Check 'cfg override' $cfg.hotkeys.quick_add 'Ctrl+Shift+Space'
    Check 'cfg default kept' $cfg.hotkeys.add_today 'Ctrl+Alt+T'
    Check 'cfg scalar' $cfg.notify 'False'
    Check 'cfg ignores _keys' $cfg.ContainsKey('_comment') 'False'
} finally { Remove-Item $cfgPath }
$hk = ConvertFrom-QcHotkey 'Ctrl+Alt+A'
Check 'hotkey mods' $hk.Modifiers 3
Check 'hotkey key' $hk.Key 'A'
Check 'hotkey digit' (ConvertFrom-QcHotkey 'Win+Shift+1').Key 'D1'
Check 'hotkey none' ($null -eq (ConvertFrom-QcHotkey '')) 'True'
$threw = $false; try { ConvertFrom-QcHotkey 'A' | Out-Null } catch { $threw = $true }
Check 'hotkey needs modifier' $threw 'True'

if ($script:failed) { Write-Host "`n$script:failed failed"; exit 1 }
Write-Host "`nall passed"

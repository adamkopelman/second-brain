# QuickCapture.Core.ps1 — the parts of Quick Capture that don't need Windows: parse what was typed
# into the popup and write it to 00 Inbox/ in the vault's capture format (see the gtd-capture skill
# and 30 Resources/GTD System.md). Dot-sourced by quick_capture.ps1 and the tests.
# Written for Windows PowerShell 5.1 (built into Windows) — no PS7-only syntax.

$script:Weekdays = @{
    sun = 0; sunday = 0; mon = 1; monday = 1; tue = 2; tues = 2; tuesday = 2; wed = 3; wednesday = 3
    thu = 4; thur = 4; thurs = 4; thursday = 4; fri = 5; friday = 5; sat = 6; saturday = 6
}
$script:Contexts = @('computer', 'phone', 'errands', 'home', 'office', 'anywhere', 'agenda', 'unknown')

function ConvertTo-QcSlug([string]$Text) {
    # Same rule as dashboard_writer._slugify: keep letters in any script, collapse the rest to "-".
    $slug = ([regex]::Replace($Text.ToLowerInvariant(), '[\W_]+', '-')).Trim('-')
    if (-not $slug) { $slug = 'item' }
    if ($slug.Length -gt 40) { $slug = $slug.Substring(0, 40).TrimEnd('-') }
    return $slug
}

function Resolve-QcDate([string]$Word, [datetime]$Today) {
    # A date word -> [datetime], or $null if it isn't one. today/tod, tomorrow/tmr/tom,
    # a weekday (the next one after today), +N (in N days), next-week (next Monday),
    # YYYY-MM-DD, or MM-DD / M/D (this year, or next year if that's already past).
    $w = $Word.ToLowerInvariant()
    $Today = $Today.Date
    switch -regex ($w) {
        '^(today|tod|tdy)$' { return $Today }
        '^(tomorrow|tmr|tom|tmrw)$' { return $Today.AddDays(1) }
        '^(next-?week|nw)$' { $d = $Today.AddDays(1); while ($d.DayOfWeek -ne 'Monday') { $d = $d.AddDays(1) }; return $d }
        '^\+(\d{1,3})d?$' { return $Today.AddDays([int]$Matches[1]) }
        '^(\d{4})-(\d{1,2})-(\d{1,2})$' {
            try { return New-Object DateTime ([int]$Matches[1]), ([int]$Matches[2]), ([int]$Matches[3]) } catch { return $null }
        }
        '^(\d{1,2})[-/](\d{1,2})$' {
            try { $d = New-Object DateTime $Today.Year, ([int]$Matches[1]), ([int]$Matches[2]) } catch { return $null }
            if ($d -lt $Today) { $d = $d.AddYears(1) }
            return $d
        }
    }
    if ($script:Weekdays.ContainsKey($w)) {
        $d = $Today.AddDays(1)
        while ([int]$d.DayOfWeek -ne $script:Weekdays[$w]) { $d = $d.AddDays(1) }
        return $d
    }
    return $null
}

function ConvertFrom-QcText {
    <#
      Parse a quick-add line, TickTick-style:
        Call the dentist #phone !fri ^2026-10-31
      #tag      kept as a tag (#phone, #evening, #waiting, …)
      !when     When  -> [scheduled:: ]   (!today, !tmr, !fri, !+3, !10-20, !2026-10-20)
      ^date     Deadline -> [due:: ]      (same date words)
      Mode 'today' schedules it for today unless a !when says otherwise, and marks it #next.
      Returns a hashtable: Title, Tags, Scheduled, Due, Line, Errors.
    #>
    param([string]$Text, [ValidateSet('inbox', 'today')][string]$Mode = 'inbox', [datetime]$Today = (Get-Date))
    $words = New-Object System.Collections.Generic.List[string]
    $tags = New-Object System.Collections.Generic.List[string]
    $errors = New-Object System.Collections.Generic.List[string]
    $scheduled = $null; $due = $null
    foreach ($tok in ($Text.Trim() -split '\s+')) {
        if (-not $tok) { continue }
        if ($tok -match '^#([\w/-]+)$') {
            if (-not $tags.Contains($Matches[1])) { $tags.Add($Matches[1]) }
        } elseif ($tok -match '^!(.+)$') {
            $d = Resolve-QcDate $Matches[1] $Today
            if ($d) { $scheduled = $d } else { $errors.Add("unknown date '$tok'"); $words.Add($tok) }
        } elseif ($tok -match '^\^(.+)$') {
            $d = Resolve-QcDate $Matches[1] $Today
            if ($d) { $due = $d } else { $errors.Add("unknown date '$tok'"); $words.Add($tok) }
        } else {
            $words.Add($tok)
        }
    }
    if ($Mode -eq 'today') {
        if (-not $scheduled) { $scheduled = $Today.Date }
        $hasStatus = $tags | Where-Object { $_ -in @('next', 'waiting', 'someday') }
        if (-not $hasStatus) { $tags.Add('next') }
        $hasContext = $tags | Where-Object { $_ -in $script:Contexts }
        if (-not $hasContext) { $tags.Add('anywhere') }
    }
    if (($tags -contains 'waiting')) { $since = $Today.Date } else { $since = $null }

    $title = ($words -join ' ').Trim()
    $parts = @("- [ ] $title")
    foreach ($t in $tags) { $parts += "#$t" }
    if ($scheduled) { $parts += "[scheduled:: $($scheduled.ToString('yyyy-MM-dd'))]" }
    if ($due) { $parts += "[due:: $($due.ToString('yyyy-MM-dd'))]" }
    if ($since) { $parts += "[since:: $($since.ToString('yyyy-MM-dd'))]" }
    return @{
        Title = $title; Tags = @($tags); Scheduled = $scheduled; Due = $due
        Line = ($parts -join ' '); Errors = @($errors)
    }
}

function Format-QcPreview($Parsed, [string]$Mode = 'inbox') {
    # One line under the popup's text box: where it's going and what was understood.
    if ($Mode -eq 'today') { $where = 'Today' } else { $where = 'Inbox' }
    $bits = @($where)
    if ($Parsed.Scheduled) { $bits += 'When ' + $Parsed.Scheduled.ToString('ddd MMM d') }
    if ($Parsed.Due) { $bits += 'Deadline ' + $Parsed.Due.ToString('ddd MMM d') }
    if ($Parsed.Tags.Count) { $bits += (($Parsed.Tags | ForEach-Object { "#$_" }) -join ' ') }
    $out = $bits -join '  ·  '
    if ($Parsed.Errors.Count) { $out += '  ·  ⚠ ' + ($Parsed.Errors -join ', ') }
    return $out
}

function Write-QcFile([string]$Path, [string]$Content) {
    # UTF-8 without a BOM (PowerShell 5.1's -Encoding UTF8 adds one, which breaks frontmatter).
    [System.IO.File]::WriteAllText($Path, $Content, (New-Object System.Text.UTF8Encoding $false))
}

function New-QcCapture {
    <#
      Write one capture to <Vault>/00 Inbox/<date> <slug>.md, never overwriting.
      -Text is a quick-add line (parsed with ConvertFrom-QcText) unless -Note, in which case it's
      written as-is as a plain note (clipboard captures: links, snippets, multi-line text).
      Returns the vault-relative path.
    #>
    param(
        [Parameter(Mandatory)][string]$Vault,
        [Parameter(Mandatory)][string]$Text,
        [ValidateSet('inbox', 'today')][string]$Mode = 'inbox',
        [switch]$Note,
        [datetime]$Today = (Get-Date)
    )
    $Text = $Text.Trim()
    if (-not $Text) { throw 'nothing to capture' }
    if ($Note) {
        $body = ($Text -replace "`r`n", "`n")
        $nameFrom = ($body -split "`n")[0]
    } else {
        $p = ConvertFrom-QcText -Text $Text -Mode $Mode -Today $Today
        if (-not $p.Title) { throw 'nothing to capture' }
        $body = $p.Line
        $nameFrom = $p.Title
    }
    $date = $Today.ToString('yyyy-MM-dd')
    $inbox = Join-Path $Vault '00 Inbox'
    if (-not (Test-Path -LiteralPath $inbox)) { New-Item -ItemType Directory -Path $inbox | Out-Null }
    $slug = ConvertTo-QcSlug ($nameFrom -replace 'https?://', '')
    $name = "$date $slug.md"
    $n = 2
    while (Test-Path -LiteralPath (Join-Path $inbox $name)) { $name = "$date $slug-$n.md"; $n++ }
    $content = "---`ntype: inbox`ncaptured: $date`n---`n$body`n"
    Write-QcFile (Join-Path $inbox $name) $content
    return "00 Inbox/$name"
}

function Get-QcConfig([string]$Path) {
    # Defaults, overridden by whatever the JSON file sets (missing file = all defaults).
    $cfg = @{
        vault          = ''
        dashboard_url  = 'http://localhost:8787'
        start_dashboard_server = $true
        python         = 'python'
        hotkeys        = @{
            quick_add     = 'Ctrl+Alt+A'
            add_today     = 'Ctrl+Alt+T'
            clipboard     = 'Ctrl+Alt+V'
            dashboard     = 'Ctrl+Alt+D'
        }
        notify         = $true
    }
    if ($Path -and (Test-Path -LiteralPath $Path)) {
        $json = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($prop in $json.PSObject.Properties) {
            if ($prop.Name -eq 'hotkeys' -and $prop.Value) {
                foreach ($hk in $prop.Value.PSObject.Properties) { $cfg.hotkeys[$hk.Name] = [string]$hk.Value }
            } elseif (-not $prop.Name.StartsWith('_')) {
                $cfg[$prop.Name] = $prop.Value
            }
        }
    }
    return $cfg
}

function ConvertFrom-QcHotkey([string]$Spec) {
    # "Ctrl+Alt+A" -> @{ Modifiers = <MOD_* flags>; Key = 'A' }. Key names are System.Windows.Forms.Keys
    # names (A, F9, Space, D1 for the 1 key, OemPeriod, …); an empty spec means "no hotkey".
    if (-not $Spec -or -not $Spec.Trim()) { return $null }
    $mods = 0; $key = $null
    foreach ($part in ($Spec -split '\+')) {
        switch -regex ($part.Trim().ToLowerInvariant()) {
            '^(ctrl|control)$' { $mods = $mods -bor 0x2; continue }
            '^alt$' { $mods = $mods -bor 0x1; continue }
            '^shift$' { $mods = $mods -bor 0x4; continue }
            '^(win|windows)$' { $mods = $mods -bor 0x8; continue }
            '^\d$' { $key = 'D' + $part.Trim(); continue }
            default { $key = $part.Trim() }
        }
    }
    if (-not $key) { throw "hotkey '$Spec' has no key" }
    if ($mods -eq 0) { throw "hotkey '$Spec' needs at least one of Ctrl/Alt/Shift/Win" }
    return @{ Modifiers = $mods; Key = $key }
}

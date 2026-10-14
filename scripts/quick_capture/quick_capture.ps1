<#
.SYNOPSIS
  Quick Capture — TickTick-style global keyboard shortcuts that add tasks to this vault's inbox,
  from any app on Windows. Runs in the system tray; nothing to install (Windows PowerShell 5.1).

.DESCRIPTION
  Default shortcuts (change them in quick_capture.config.json):
    Ctrl+Alt+A  Quick add -> 00 Inbox/
    Ctrl+Alt+T  Quick add -> Today (#next, [scheduled:: today])
    Ctrl+Alt+V  Capture the clipboard (copied text/link) -> 00 Inbox/, no popup
    Ctrl+Alt+D  Open the local dashboard (starts scripts/dashboard_server.py if it isn't running)
  In the popup: #tag, !when (!today !tmr !fri !+3 !10-20), ^deadline (same words).
  Enter saves · Shift+Enter saves and keeps the box open for the next one · Esc cancels.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\quick_capture\quick_capture.ps1 -Install
  Adds it to Windows startup and starts it now. -Uninstall removes it; no switch = just run.
#>
param(
    [switch]$Install,
    [switch]$Uninstall,
    [string]$Config = (Join-Path $PSScriptRoot 'quick_capture.config.json')
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'QuickCapture.Core.ps1')

$ShortcutPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'GTD Quick Capture.lnk'

function Stop-QcRunning {
    # Any other copy of this script that's running (the tray app) — matched on its command line.
    $me = $PID
    Get-CimInstance Win32_Process -Filter "Name = 'powershell.exe' OR Name = 'pwsh.exe'" |
        Where-Object { $_.ProcessId -ne $me -and $_.CommandLine -like '*quick_capture.ps1*' -and
                       $_.CommandLine -notlike '*-Install*' -and $_.CommandLine -notlike '*-Uninstall*' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

if ($Install -or $Uninstall) {
    Stop-QcRunning
    if (Test-Path -LiteralPath $ShortcutPath) { Remove-Item -LiteralPath $ShortcutPath -Force }
    if ($Uninstall) { Write-Host 'Quick Capture removed from startup and stopped.'; return }
    $psExe = Join-Path $PSHOME 'powershell.exe'
    if (-not (Test-Path $psExe)) { $psExe = (Get-Process -Id $PID).Path }
    $args_ = "-NoProfile -STA -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    $sh = New-Object -ComObject WScript.Shell
    $lnk = $sh.CreateShortcut($ShortcutPath)
    $lnk.TargetPath = $psExe
    $lnk.Arguments = $args_
    $lnk.WorkingDirectory = $PSScriptRoot
    $lnk.WindowStyle = 7  # minimized — with -WindowStyle Hidden there's no window at all
    $lnk.Description = 'GTD second brain: global shortcuts to capture tasks'
    $lnk.Save()
    Start-Process -FilePath $psExe -ArgumentList $args_ -WindowStyle Hidden
    $cfg = Get-QcConfig $Config
    Write-Host "Quick Capture installed — it starts with Windows and is running now (tray icon)."
    foreach ($k in $cfg.hotkeys.Keys) { Write-Host ("  {0,-12} {1}" -f $cfg.hotkeys[$k], $k) }
    return
}

# ---------------------------------------------------------------- the tray app
Add-Type -AssemblyName System.Windows.Forms, System.Drawing

# One copy at a time: a second launch just exits.
$mutex = New-Object System.Threading.Mutex($false, 'Local\GtdSecondBrainQuickCapture')
if (-not $mutex.WaitOne(0)) { return }

$cfg = Get-QcConfig $Config
$Vault = if ($cfg.vault) { [string]$cfg.vault } else { (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path }
if (-not (Test-Path -LiteralPath (Join-Path $Vault '00 Inbox'))) {
    [System.Windows.Forms.MessageBox]::Show("No '00 Inbox' folder in $Vault.`nSet ""vault"" in $Config.",
        'Quick Capture') | Out-Null
    return
}

Add-Type -ReferencedAssemblies System.Windows.Forms -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Windows.Forms;
public class QcHotkeys : NativeWindow, IDisposable {
    [DllImport("user32.dll", SetLastError = true)] static extern bool RegisterHotKey(IntPtr h, int id, uint mods, uint vk);
    [DllImport("user32.dll")] static extern bool UnregisterHotKey(IntPtr h, int id);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    const int WM_HOTKEY = 0x0312;
    const uint MOD_NOREPEAT = 0x4000;
    int next = 1;
    public event Action<int> Pressed;
    public QcHotkeys() { CreateHandle(new CreateParams()); }
    // Returns the hotkey's id, or 0 if Windows refused it (usually: another app already owns it).
    public int Add(uint mods, Keys key) {
        int id = next++;
        return RegisterHotKey(Handle, id, mods | MOD_NOREPEAT, (uint)key) ? id : 0;
    }
    protected override void WndProc(ref Message m) {
        if (m.Msg == WM_HOTKEY && Pressed != null) Pressed(m.WParam.ToInt32());
        base.WndProc(ref m);
    }
    public void Dispose() { for (int i = 1; i < next; i++) UnregisterHotKey(Handle, i); DestroyHandle(); }
}
'@

# --- tray icon: a little inbox drawn in code, so there's no .ico to ship
function New-QcIcon {
    $bmp = New-Object System.Drawing.Bitmap 32, 32
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = 'AntiAlias'
    $g.FillEllipse((New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(37, 99, 235))), 1, 1, 30, 30)
    $pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::White), 3
    $g.DrawLine($pen, 16, 8, 16, 22); $g.DrawLine($pen, 9, 15, 23, 15)
    $g.Dispose()
    return [System.Drawing.Icon]::FromHandle($bmp.GetHicon())
}

$tray = New-Object System.Windows.Forms.NotifyIcon
$tray.Icon = New-QcIcon
$tray.Text = 'GTD Quick Capture'
$tray.Visible = $true

function Show-QcToast([string]$Title, [string]$Text, [string]$Kind = 'Info') {
    if (-not $cfg.notify -and $Kind -eq 'Info') { return }
    $tray.ShowBalloonTip(2500, $Title, $Text, [System.Windows.Forms.ToolTipIcon]::$Kind)
}

# --- the quick-add popup
$Accent = [System.Drawing.Color]::FromArgb(37, 99, 235)
$form = New-Object System.Windows.Forms.Form
$form.FormBorderStyle = 'None'
$form.StartPosition = 'Manual'
$form.ShowInTaskbar = $false
$form.TopMost = $true
$form.KeyPreview = $true
$form.BackColor = [System.Drawing.Color]::White
$form.Size = New-Object System.Drawing.Size 640, 112
$form.Padding = New-Object System.Windows.Forms.Padding 2
$form.add_Paint({ param($s, $e)
    $e.Graphics.DrawRectangle((New-Object System.Drawing.Pen $Accent, 2), 1, 1, $s.Width - 2, $s.Height - 2) })

$head = New-Object System.Windows.Forms.Label
$head.Font = New-Object System.Drawing.Font 'Segoe UI Semibold', 10
$head.ForeColor = $Accent
$head.SetBounds(18, 12, 600, 22)
$box = New-Object System.Windows.Forms.TextBox
$box.Font = New-Object System.Drawing.Font 'Segoe UI', 14
$box.BorderStyle = 'None'
$box.SetBounds(18, 40, 604, 30)
$hint = New-Object System.Windows.Forms.Label
$hint.Font = New-Object System.Drawing.Font 'Segoe UI', 9
$hint.ForeColor = [System.Drawing.Color]::FromArgb(107, 114, 128)
$hint.SetBounds(18, 80, 604, 20)
$form.Controls.AddRange(@($head, $box, $hint))

$script:mode = 'inbox'
$HelpLine = '#tag   !when (!tmr !fri !+3)   ^deadline   ·   Enter save   ·   Shift+Enter save + next   ·   Esc'
function Update-QcHint {
    if ($box.Text.Trim()) { $hint.Text = Format-QcPreview (ConvertFrom-QcText $box.Text -Mode $script:mode) $script:mode }
    else { $hint.Text = $HelpLine }
}
$box.add_TextChanged({ Update-QcHint })

function Show-QcPopup([string]$Mode) {
    $script:mode = $Mode
    $head.Text = if ($Mode -eq 'today') { '★  Add to Today' } else { '📥  Add to Inbox' }
    $box.Text = ''
    Update-QcHint
    $screen = [System.Windows.Forms.Screen]::FromPoint([System.Windows.Forms.Cursor]::Position).WorkingArea
    $form.Location = New-Object System.Drawing.Point ($screen.X + [int](($screen.Width - $form.Width) / 2)), ($screen.Y + [int]($screen.Height / 4))
    $form.Show()
    $form.Activate()
    [QcHotkeys]::SetForegroundWindow($form.Handle) | Out-Null
    $box.Focus() | Out-Null
}

$form.add_KeyDown({ param($s, $e)
    if ($e.KeyCode -eq 'Escape') { $form.Hide(); $e.SuppressKeyPress = $true; return }
    if ($e.KeyCode -ne 'Return') { return }
    $e.SuppressKeyPress = $true
    if (-not $box.Text.Trim()) { $form.Hide(); return }
    try {
        $rel = New-QcCapture -Vault $Vault -Text $box.Text -Mode $script:mode
        $title = (ConvertFrom-QcText $box.Text).Title
        if ($e.Shift) { $box.Text = ''; $hint.Text = "✓ Saved: $title — next one…" }
        else { $form.Hide(); Show-QcToast 'Captured' "$title`n→ $rel" }
    } catch {
        $hint.Text = "⚠ $($_.Exception.Message)"
    }
})
$form.add_Deactivate({ if ($form.Visible -and -not $box.Text.Trim()) { $form.Hide() } })

function Invoke-QcClipboard {
    $text = [System.Windows.Forms.Clipboard]::GetText()
    if (-not $text -or -not $text.Trim()) { Show-QcToast 'Nothing to capture' 'The clipboard has no text.' 'Warning'; return }
    try {
        # one short line reads as a task; links and longer snippets go in as a plain note
        $oneLine = ($text.Trim() -notmatch "`n") -and ($text.Trim().Length -le 120) -and ($text -notmatch '^\s*https?://')
        if ($oneLine) { $rel = New-QcCapture -Vault $Vault -Text $text }
        else { $rel = New-QcCapture -Vault $Vault -Text $text -Note }
        Show-QcToast 'Clipboard captured' $rel
    } catch { Show-QcToast 'Capture failed' $_.Exception.Message 'Error' }
}

function Open-QcDashboard {
    $url = [string]$cfg.dashboard_url
    $uri = [Uri]$url
    $up = $false
    try { $c = New-Object System.Net.Sockets.TcpClient; $c.Connect($uri.Host, $uri.Port); $up = $true; $c.Close() } catch {}
    if (-not $up -and $cfg.start_dashboard_server) {
        $server = Join-Path $Vault 'scripts\dashboard_server.py'
        try {
            Start-Process -FilePath $cfg.python -ArgumentList "`"$server`" `"$Vault`" --port $($uri.Port)" -WindowStyle Hidden
            Start-Sleep -Milliseconds 1500
        } catch { Show-QcToast 'Dashboard' "Couldn't start the dashboard server: $($_.Exception.Message)" 'Warning' }
    }
    Start-Process $url
}

# --- hotkeys
$actions = [ordered]@{
    quick_add = @{ Label = 'Quick add to Inbox'; Run = { Show-QcPopup 'inbox' } }
    add_today = @{ Label = 'Add to Today'; Run = { Show-QcPopup 'today' } }
    clipboard = @{ Label = 'Capture clipboard'; Run = { Invoke-QcClipboard } }
    dashboard = @{ Label = 'Open dashboard'; Run = { Open-QcDashboard } }
}
$hotkeys = New-Object QcHotkeys
$byId = @{}
$failed = @()
foreach ($name in $actions.Keys) {
    $spec = $cfg.hotkeys[$name]
    $actions[$name].Spec = $spec
    try { $hk = ConvertFrom-QcHotkey $spec } catch { $failed += "$spec ($($_.Exception.Message))"; continue }
    if (-not $hk) { continue }
    $id = $hotkeys.Add([uint32]$hk.Modifiers, [System.Windows.Forms.Keys]$hk.Key)
    if ($id) { $byId[$id] = $actions[$name].Run } else { $failed += "$spec (taken by another app)" }
}
$hotkeys.add_Pressed({ param($id)
    if (-not $byId.ContainsKey($id)) { return }
    try { & $byId[$id] } catch { Show-QcToast 'Quick Capture' $_.Exception.Message 'Error' }
})

# --- tray menu
$menu = New-Object System.Windows.Forms.ContextMenuStrip
foreach ($name in $actions.Keys) {
    $a = $actions[$name]
    $item = $menu.Items.Add($a.Label)
    $item.ShortcutKeyDisplayString = $a.Spec
    $item.Tag = $a.Run
    $item.add_Click({ param($s) & $s.Tag })
}
[void]$menu.Items.Add('-')
$menu.Items.Add('Open inbox folder').add_Click({ Start-Process explorer.exe "`"$(Join-Path $Vault '00 Inbox')`"" })
$menu.Items.Add('Edit shortcuts…').add_Click({ Start-Process notepad.exe "`"$Config`"" })
[void]$menu.Items.Add('-')
$menu.Items.Add('Exit').add_Click({ [System.Windows.Forms.Application]::Exit() })
$tray.ContextMenuStrip = $menu
$tray.add_MouseClick({ param($s, $e) if ($e.Button -eq 'Left') { Show-QcPopup 'inbox' } })

if ($failed) { Show-QcToast 'Some shortcuts unavailable' ($failed -join "`n") 'Warning' }
else { Show-QcToast 'Quick Capture is running' ("{0} to add a task" -f $cfg.hotkeys.quick_add) }

try {
    [System.Windows.Forms.Application]::Run()
} finally {
    $hotkeys.Dispose()
    $tray.Visible = $false
    $tray.Dispose()
    $mutex.ReleaseMutex()
}

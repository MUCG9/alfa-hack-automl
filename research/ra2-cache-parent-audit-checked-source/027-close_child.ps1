param(
    [Parameter(Mandatory=$true)][string]$Python,
    [Parameter(Mandatory=$true)][string]$Closer,
    [Parameter(Mandatory=$true)][string]$Manifest,
    [Parameter(Mandatory=$true)][string]$ManifestSha,
    [Parameter(Mandatory=$true)][string]$CloserSha,
    [Parameter(Mandatory=$true)][string]$DriverSha,
    [Parameter(Mandatory=$true)][string]$CampaignSha,
    [Parameter(Mandatory=$true)][string]$ActualTool,
    [Parameter(Mandatory=$true)][int]$ActualExit,
    [Parameter(Mandatory=$true)][string]$ExitReceipt,
    [string]$ActualSession = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$shellBirth = ((Get-Process -Id $PID).StartTime.ToUniversalTime().Ticks - 621355968000000000L) / 10000000.0
$birthText = $shellBirth.ToString('R', [System.Globalization.CultureInfo]::InvariantCulture)
$nativeArgs = @('-B', '-X', 'utf8', $Closer,
    '--manifest', $Manifest, '--manifest-sha256', $ManifestSha,
    '--self-sha256', $CloserSha, '--driver-sha256', $DriverSha,
    '--campaign-sha256', $CampaignSha, '--actual-tool-evidence', $ActualTool,
    '--actual-exit-code', $ActualExit.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '--launch-parent-pid', $PID.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '--launch-parent-create-time', $birthText)
if ($ActualSession -ne '') { $nativeArgs += @('--actual-exec-session', $ActualSession) }
& $Python @nativeArgs
$nativeExit = $LASTEXITCODE
if ($null -eq $nativeExit) { throw 'native_exit_unobserved' }
$record = @{schema='postfailure-standard-artifact-actual-native-closer-exit-v1';
    actual_native_exit_code=[int]$nativeExit; shell=@{pid=$PID;create_time=$shellBirth}}
$raw = ($record | ConvertTo-Json -Depth 4)
$stream = [System.IO.File]::Open($ExitReceipt, [System.IO.FileMode]::CreateNew,
    [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read)
try {
    $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($raw)
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Flush()
} finally { $stream.Dispose() }
exit $nativeExit

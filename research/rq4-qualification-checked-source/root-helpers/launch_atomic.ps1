param(
    [Parameter(Mandatory=$true)][string]$Python,
    [Parameter(Mandatory=$true)][string]$Authority,
    [Parameter(Mandatory=$true)][string]$AuthoritySha,
    [Parameter(Mandatory=$true)][int]$ActualExit,
    [Parameter(Mandatory=$true)][string]$ActualTool,
    [string]$ActualSession = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($ActualExit -ne 0) { throw 'actual_driver_exit0_required' }
if ((Get-FileHash -LiteralPath $Authority -Algorithm SHA256).Hash.ToLowerInvariant() -ne $AuthoritySha) {
    throw 'reviewed_authority_changed'
}
$auth = Get-Content -LiteralPath $Authority -Raw -Encoding UTF8 | ConvertFrom-Json
if ($auth.readiness -ne 'READY_REVIEWED_FROZEN' -or @($auth.missing_bindings).Count -ne 0) { throw 'NOT_READY' }
if ($Python -ne $auth.refs.python.path -or
    (Get-FileHash -LiteralPath $Python -Algorithm SHA256).Hash.ToLowerInvariant() -ne $auth.refs.python.sha256) {
    throw 'pinned_interpreter_required'
}
foreach ($item in $auth.refs.PSObject.Properties) {
    if ((Get-FileHash -LiteralPath $item.Value.path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.Value.sha256) {
        throw 'reviewed_launch_source_changed'
    }
}
if ($PSCommandPath -ne $auth.refs.launch_script.path) { throw 'fixed_launch_script_required' }
$shellBirth = ((Get-Process -Id $PID).StartTime.ToUniversalTime().Ticks - 621355968000000000L) / 10000000.0
$birth = $shellBirth.ToString('R', [System.Globalization.CultureInfo]::InvariantCulture)
$common = @('--authority', $Authority, '--authority-sha256', $AuthoritySha,
    '--actual-exit-code', $ActualExit.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '--actual-tool', $ActualTool, '--launch-parent-pid', $PID.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '--launch-parent-create-time', $birth)
if ($ActualSession -ne '') { $common += @('--actual-session', $ActualSession) }
& $Python '-B' '-X' 'utf8' $auth.refs.binder.path @common
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$binding = Join-Path (Split-Path -Parent $auth.output) 'private/rq4-atomic-binding.ready-r1.json'
$bindingSha = (Get-FileHash -LiteralPath $binding -Algorithm SHA256).Hash.ToLowerInvariant()
$atomicArgs = @('--binding', $binding, '--binding-sha256', $bindingSha,
    '--self-sha256', $auth.refs.atomic_source.sha256,
    '--actual-exit-code', $ActualExit.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '--actual-tool-evidence', $ActualTool,
    '--launch-parent-pid', $PID.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '--launch-parent-create-time', $birth)
if ($ActualSession -ne '') { $atomicArgs += @('--actual-exec-session', $ActualSession) }
& $Python '-B' '-X' 'utf8' $auth.refs.atomic_source.path @atomicArgs
$actualWrapperExit = $LASTEXITCODE
if ($null -eq $actualWrapperExit) { throw 'actual_wrapper_exit_unobserved' }
# This is a native exit receipt only. Root supplies the actual tool evidence to
# confirm_post_tool.py after this tool completes; this script cannot invent it.
$receipt = Join-Path $auth.output 'root-launch-native-exit.json'
$value = @{schema='rq4-root-launch-native-exit-v1'; actual_wrapper_exit=[int]$actualWrapperExit;
    binding_sha256=$bindingSha; authority_sha256=$AuthoritySha; shell=@{pid=$PID;create_time=$shellBirth}}
$stream = [System.IO.File]::Open($receipt, [System.IO.FileMode]::CreateNew,
    [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read)
try {
    $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes(($value | ConvertTo-Json -Depth 5))
    $stream.Write($bytes, 0, $bytes.Length); $stream.Flush()
} finally { $stream.Dispose() }
exit $actualWrapperExit

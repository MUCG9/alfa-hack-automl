param(
    [Parameter(Mandatory=$true)][ValidateSet('Close','Post')][string]$Mode,
    [Parameter(Mandatory=$true)][string]$SelfSha256,
    [string]$Template = '',
    [string]$TemplateSha256 = '',
    [int]$ActualMainExit = -2147483648,
    [string]$ActualMainTool = '',
    [string]$ActualMainSession = '',
    [int]$ActualWrapperExit = -2147483648,
    [string]$ActualWrapperTool = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Need([bool]$Value, [string]$Code) {
    if (-not $Value) { throw $Code }
}
function HashFile([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Absolute([string]$Path) {
    return [IO.Path]::IsPathRooted($Path) -and ([IO.Path]::GetFullPath($Path) -ceq $Path)
}
function Regular([string]$Path) {
    Need (Absolute $Path) 'absolute_metadata_or_source_path_required'
    $item = Get-Item -LiteralPath $Path -Force
    Need (-not $item.PSIsContainer -and ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'regular_nonreparse_file_required'
}
function ReadJson([string]$Path, [long]$Limit) {
    Regular $Path
    Need ((Get-Item -LiteralPath $Path).Length -le $Limit) 'bounded_metadata_file_required'
    return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json)
}
function ShaText([string]$Value) {
    return $Value -cmatch '^[0-9a-f]{64}$'
}
function ActualTool([string]$Value) {
    return -not [string]::IsNullOrWhiteSpace($Value) -and $Value -cne 'undefined' -and $Value -notmatch 'PENDING'
}
function FiniteNumber($Value) {
    if (-not ($Value -is [int] -or $Value -is [long] -or $Value -is [double] -or $Value -is [decimal])) { return $false }
    return -not [double]::IsNaN([double]$Value) -and -not [double]::IsInfinity([double]$Value)
}
function Pins($Object) {
    $result = [Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
    foreach ($entry in $Object.PSObject.Properties) {
        Need ((Absolute $entry.Name) -and $entry.Value -is [string] -and (ShaText $entry.Value)) 'closed_absolute_source_pin_map_required'
        $result.Add($entry.Name, $entry.Value)
    }
    Need ($result.Count -gt 0 -and $result.Count -le 4096) 'existing_source_pin_limit_required'
    return ,$result
}
function Role($Ref, [string]$ExpectedPath, $Map) {
    Need ($Ref.path -ceq $ExpectedPath -and (ShaText $Ref.sha256)) 'fixed_role_source_path_and_SHA_required'
    Need ($Map.ContainsKey($ExpectedPath) -and $Map[$ExpectedPath] -ceq $Ref.sha256) 'role_must_equal_original_pin'
    Regular $ExpectedPath
    Need ((HashFile $ExpectedPath) -ceq $Ref.sha256) 'role_source_bytes_changed'
}
function SourceMap($Binding, [string]$Work, [string]$Outer, [string]$SelfPath) {
    Need ($Binding.schema -ceq 'qwen-three-hour-atomic-root-private-v1') 'exact_existing_atomic_schema_required'
    Need ($Binding.output -ceq (Join-Path $Work 'qh5') -and $Binding.expected_output_work_relative -ceq 'qh5') 'fixed_QH5_output_required'
    $map = Pins $Binding.immutable_files
    Need ($map.ContainsKey($SelfPath) -and $map[$SelfPath] -ceq $SelfSha256) 'native_bootstrap_original_source_pin_required'
    Role $Binding.driver (Join-Path $Outer 'run_campaign.py') $map
    Role $Binding.closer (Join-Path $Outer 'close_controller.py') $map
    Role $Binding.post_tool (Join-Path $Outer 'confirm_post_tool.py') $map
    Role $Binding.python (Join-Path (Join-Path (Join-Path $Work 'venv') 'Scripts') 'python.exe') $map
    $shellPath = (Get-Process -Id $PID).Path
    Role $Binding.powershell $shellPath $map
    Need ((Absolute $Binding.manifest.path) -and $Binding.manifest.path.StartsWith((Join-Path $Work 'private') + [IO.Path]::DirectorySeparatorChar, [StringComparison]::Ordinal)) 'main_manifest_inside_exact_private_required'
    Role $Binding.manifest $Binding.manifest.path $map
    foreach ($review in @($Binding.independent_source_review, $Binding.qualification_source_review)) {
        Need ((Absolute $review.path) -and $review.path.StartsWith($Work + [IO.Path]::DirectorySeparatorChar, [StringComparison]::Ordinal)) 'review_inside_exact_WORK_required'
        Role $review $review.path $map
    }
    $wrapper = Join-Path $Outer 'run_root.py'
    Regular $wrapper
    Need ($map.ContainsKey($wrapper) -and (ShaText $map[$wrapper]) -and (HashFile $wrapper) -ceq $map[$wrapper]) 'exact_pinned_atomic_wrapper_required'
    $child = Join-Path $Outer 'close_child.ps1'
    Regular $child
    Need ((ShaText $Binding.child_script_sha256) -and $map.ContainsKey($child) -and $map[$child] -ceq $Binding.child_script_sha256 -and (HashFile $child) -ceq $Binding.child_script_sha256) 'exact_unchanged_child_script_required'
    Need ($Binding.campaign.path -ceq (Join-Path (Join-Path $Work 'qh5') 'campaign.json')) 'fixed_terminal_campaign_path_required'
    return ,$map
}
function Campaign($Binding) {
    $path = $Binding.campaign.path
    Regular $path
    $before = HashFile $path
    $record = ReadJson $path 33554432
    Need ((HashFile $path) -ceq $before) 'campaign_changed_during_native_projection'
    $keys = @('status','cleanup_confirmed','source_unchanged','temporary_cleanup_confirmed','start_unix','start_monotonic',
        'absolute_deadline_unix','common_deadline_monotonic','final_deadline_monotonic')
    foreach ($key in $keys) { Need ($null -ne $record.PSObject.Properties[$key]) 'terminal_campaign_scalar_missing' }
    foreach ($key in @('start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic','final_deadline_monotonic')) {
        Need (FiniteNumber $record.$key) 'finite_original_campaign_clock_required'
    }
    Need ($record.absolute_deadline_unix -eq $record.start_unix + 10800 -and $record.common_deadline_monotonic -eq $record.start_monotonic + 10800) 'same_original10800_required'
    $now = ([DateTime]::UtcNow.Ticks - 621355968000000000L) / 10000000.0
    Need ($now -ge $record.start_unix -and $now + 60 -lt $record.absolute_deadline_unix) 'full_closure60_inside_original_common_required'
    # Python's reviewed closure enforces both original wall and monotonic clocks.
    # Native PS does not fabricate a monotonic origin or grant another deadline.
    return @{record=$record; sha256=$before}
}

try {
    $self = [IO.Path]::GetFullPath($PSCommandPath)
    Regular $self
    Need ((ShaText $SelfSha256) -and (HashFile $self) -ceq $SelfSha256) 'exact_native_bootstrap_source_required'
    $work = Split-Path -Parent $PSScriptRoot
    $outer = Join-Path $work 'qwen-three-hour-outer-next-dev-r10'
    $output = Join-Path $work 'qh5'
    $bindingPath = Join-Path (Join-Path $work 'private') 'qh5-atomic-root-binding-r1.json'
    foreach ($directory in @($PSScriptRoot, $outer, $output, (Join-Path $work 'private'))) {
        $item = Get-Item -LiteralPath $directory -Force
        Need ($item.PSIsContainer -and ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) 'exact_nonreparse_operational_directory_required'
    }
    $shellBirth = ((Get-Process -Id $PID).StartTime.ToUniversalTime().Ticks - 621355968000000000L) / 10000000.0
    $birthText = $shellBirth.ToString('R', [Globalization.CultureInfo]::InvariantCulture)
    $pidText = $PID.ToString([Globalization.CultureInfo]::InvariantCulture)

    if ($Mode -ceq 'Close') {
        Regular $Template
        Need ((Absolute $Template) -and $Template.StartsWith((Join-Path $work 'private') + [IO.Path]::DirectorySeparatorChar, [StringComparison]::Ordinal) -and (ShaText $TemplateSha256) -and (HashFile $Template) -ceq $TemplateSha256) 'exact_root_hosted_template_required'
        $binding = ReadJson $Template 1048576
        Need ((HashFile $Template) -ceq $TemplateSha256) 'root_template_changed_during_native_read'
        Need ($binding.readiness -ceq 'NOT_READY' -and @($binding.missing_bindings).Count -eq 1 -and $binding.missing_bindings[0] -ceq 'actual_campaign_sha256' -and $null -eq $binding.campaign.sha256) 'only_actual_terminal_campaign_may_be_missing'
        $pins = SourceMap $binding $work $outer $self
        Need (-not $pins.ContainsKey($binding.campaign.path)) 'no_repin_of_terminal_campaign'
        Need ($ActualMainExit -ne -2147483648 -and (ActualTool $ActualMainTool)) 'actual_whole_main_exit_and_tool_required'
        Need ($ActualMainSession -eq '' -or $ActualMainSession -cmatch '^[0-9]+$') 'actual_session_only_when_supplied'
        $observed = Campaign $binding
        $campaign = $observed.record
        $campaignSha = $observed.sha256
        Need (ShaText $campaignSha) 'actual_terminal_campaign_hash_required'
        $common = @('--manifest', $binding.manifest.path, '--manifest-sha256', $binding.manifest.sha256,
            '--self-sha256', $binding.closer.sha256, '--driver-sha256', $binding.driver.sha256,
            '--campaign-sha256', $campaignSha, '--actual-exit-code', $ActualMainExit.ToString([Globalization.CultureInfo]::InvariantCulture),
            '--actual-tool-evidence', $ActualMainTool, '--launch-parent-pid', $pidText, '--launch-parent-create-time', $birthText)
        if ($ActualMainSession -ne '') { $common += @('--actual-exec-session', $ActualMainSession) }
        if ($ActualMainExit -ne 0) {
            Need ($campaign.status -ceq 'failed') 'actual_nonzero_main_requires_failed_campaign'
            & $binding.python.path -B -X utf8 $binding.closer.path @common
        } else {
            Need ($campaign.status -ceq 'completed_pending_root' -and $campaign.cleanup_confirmed -is [bool] -and $campaign.cleanup_confirmed -eq $true -and $campaign.source_unchanged -is [bool] -and $campaign.source_unchanged -eq $true -and $campaign.temporary_cleanup_confirmed -is [bool] -and $campaign.temporary_cleanup_confirmed -eq $true) 'clean_completed_main_required'
            $now = ([DateTime]::UtcNow.Ticks - 621355968000000000L) / 10000000.0
            $finalWall = $campaign.start_unix + ($campaign.final_deadline_monotonic - $campaign.start_monotonic)
            Need ($now + 60 -lt $finalWall -and $campaign.final_deadline_monotonic -le $campaign.common_deadline_monotonic - 60) 'full_wrapper60_inside_existing_final_required'
            Need (-not (Test-Path -LiteralPath $bindingPath)) 'exclusive_new_atomic_binding_required'
            $pins.Add($binding.campaign.path, $campaignSha)
            $binding.immutable_files = $pins
            $binding.campaign.sha256 = $campaignSha
            $binding.readiness = 'READY_REVIEWED_FROZEN'
            $binding.missing_bindings = @()
            $raw = $binding | ConvertTo-Json -Depth 100
            $bytes = [Text.UTF8Encoding]::new($false).GetBytes($raw)
            Need ($bytes.Length -le 1048576) 'existing_atomic_private_byte_limit_required'
            $stream = [IO.File]::Open($bindingPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
            try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
            $bindingSha = HashFile $bindingPath
            Need ((HashFile $binding.campaign.path) -ceq $campaignSha) 'terminal_campaign_changed_before_atomic_launch'
            $wrapper = Join-Path $outer 'run_root.py'
            $nativeArgs = @('-B','-X','utf8',$wrapper,'--binding',$bindingPath,'--binding-sha256',$bindingSha,
                '--self-sha256',$pins[$wrapper],'--actual-exit-code','0','--actual-tool-evidence',$ActualMainTool,
                '--launch-parent-pid',$pidText,'--launch-parent-create-time',$birthText)
            if ($ActualMainSession -ne '') { $nativeArgs += @('--actual-exec-session',$ActualMainSession) }
            & $binding.python.path @nativeArgs
        }
    } else {
        Need ($ActualWrapperExit -eq 0 -and (ActualTool $ActualWrapperTool)) 'actual_whole_prior_wrapper_exit0_and_tool_required'
        Regular $bindingPath
        $bindingSha = HashFile $bindingPath
        $binding = ReadJson $bindingPath 1048576
        Need ((HashFile $bindingPath) -ceq $bindingSha) 'atomic_binding_changed_during_native_read'
        Need ($binding.readiness -ceq 'READY_REVIEWED_FROZEN' -and @($binding.missing_bindings).Count -eq 0) 'actual_ready_atomic_binding_required'
        $pins = SourceMap $binding $work $outer $self
        Need ((ShaText $binding.campaign.sha256) -and $pins.ContainsKey($binding.campaign.path) -and $pins[$binding.campaign.path] -ceq $binding.campaign.sha256 -and (HashFile $binding.campaign.path) -ceq $binding.campaign.sha256) 'unchanged_actual_terminal_campaign_required'
        Need ((HashFile $bindingPath) -ceq $bindingSha) 'atomic_binding_changed_before_post_launch'
        & $binding.python.path -B -X utf8 $binding.post_tool.path --binding $bindingPath --binding-sha256 $bindingSha `
            --self-sha256 $binding.post_tool.sha256 --wrapper-tool $ActualWrapperTool --wrapper-exit-code 0 `
            --launch-parent-pid $pidText --launch-parent-create-time $birthText
    }
    $nativeExit = $LASTEXITCODE
    Need ($null -ne $nativeExit) 'actual_native_terminal_exit_required'
    exit ([int]$nativeExit)
} catch {
    [Console]::Error.WriteLine('qh5_native_bootstrap_failure:' + $_.Exception.GetType().FullName)
    exit 1
}

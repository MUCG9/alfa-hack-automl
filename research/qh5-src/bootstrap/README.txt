SOURCE ONLY. The root collector must invoke & ABS/close_native.ps1 in the existing exec PowerShell; never launch an extra pwsh -File and never override policy.
Close: -Mode Close -Template ABS -TemplateSha256 SHA -SelfSha256 SHA -ActualMainExit ACTUAL_INT -ActualMainTool ACTUAL_CHUNK [-ActualMainSession ACTUAL_SESSION].
Post: NEW execPS only after actual entire Close tool exit0, using -Mode Post -SelfSha256 SHA -ActualWrapperExit 0 -ActualWrapperTool ACTUAL_CLOSE_TOOL.
Root-hosted template uses existing atomic schema, NOT_READY, exactly one missing actual_campaign_sha256, null campaign.sha256 and no campaign pin. Full keys and exact paths are in contract.json.
Close reads bounded metadata/hash natively; samePS is captured by qualified Python closer/wrapper. Post captures newPS. Preserve every tool terminal/history; integer exit and nonempty chunk are mandatory before dependent actions.
Binding output is fixed WORK/private/qh5-atomic-root-binding-r1.json with exclusive CreateNew. Source role map contains this script plus finalreviewed OuterR10/Python/PS/reviews/actualmainmanifest. No component/source/cap/finalusage relaxation.
Only PowerShell AST syntax parsing was performed by author; target script, Python helper, tests/models/provider were never executed. Actual READY/clock/values remain root-owned.

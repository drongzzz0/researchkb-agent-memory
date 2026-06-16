param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ClaudeArgs
)

. "$PSScriptRoot\claude-launcher-common.ps1"

$userConfig = Get-ClaudeUserSettings
$userSettings = $userConfig.Data
$settings = Get-PreservedClaudeSettings -UserSettings $userSettings -Model "gpt-5.4"

$envFromUser = Get-JsonProperty -Object $userSettings -Name "env"
if ($null -eq $envFromUser) {
    throw "The current Claude user settings do not contain an env block."
}

$requiredEnvKeys = @(
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "CLAUDE_CODE_SUBAGENT_MODEL"
)

$sessionEnv = @{}
foreach ($key in @(
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_CUSTOM_MODEL_OPTION",
    "ANTHROPIC_CUSTOM_MODEL_OPTION_NAME",
    "ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "CLAUDE_CODE_SUBAGENT_MODEL",
    "API_TIMEOUT_MS",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"
)) {
    $value = Get-JsonProperty -Object $envFromUser -Name $key
    if ($null -ne $value) {
        $sessionEnv[$key] = $value
    }
}

foreach ($key in $requiredEnvKeys) {
    if (-not $sessionEnv.ContainsKey($key)) {
        throw "Missing required env key in $($userConfig.Path): $key"
    }
}

Set-SessionEnv -Variables $sessionEnv

$showConfig = $ClaudeArgs -contains "--show-config"
$forwardArgs = Get-FilteredArgs -Args $ClaudeArgs -ExcludedArg "--show-config"

if ($showConfig) {
    Show-LauncherConfig `
        -EntryName "claude-gpt54" `
        -Model "gpt-5.4" `
        -BaseUrl ([string]$sessionEnv["ANTHROPIC_BASE_URL"]) `
        -AuthSource ("runtime env from " + $userConfig.Path) `
        -SettingSources "project,local + launcher overrides" `
        -ClaudePath ((Get-Command claude).Path)
    exit 0
}

Invoke-ClaudeLauncher -Settings $settings -ForwardArgs $forwardArgs

param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ClaudeArgs
)

. "$PSScriptRoot\claude-launcher-common.ps1"

if ([string]::IsNullOrWhiteSpace($env:OPENROUTER_API_KEY)) {
    throw "OPENROUTER_API_KEY is not set. This launcher needs that environment variable."
}

$userConfig = Get-ClaudeUserSettings
$userSettings = $userConfig.Data
$model = "anthropic/claude-sonnet-4.6"
$settings = Get-PreservedClaudeSettings -UserSettings $userSettings -Model $model

$apiTimeout = "600000"
$disableNoise = "1"
$userEnv = Get-JsonProperty -Object $userSettings -Name "env"

if ($null -ne $userEnv) {
    $userTimeout = Get-JsonProperty -Object $userEnv -Name "API_TIMEOUT_MS"
    $userDisableNoise = Get-JsonProperty -Object $userEnv -Name "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"

    if ($null -ne $userTimeout) {
        $apiTimeout = [string]$userTimeout
    }

    if ($null -ne $userDisableNoise) {
        $disableNoise = [string]$userDisableNoise
    }
}

$sessionEnv = @{
    ANTHROPIC_BASE_URL = "https://openrouter.ai/api"
    ANTHROPIC_AUTH_TOKEN = $env:OPENROUTER_API_KEY
    ANTHROPIC_API_KEY = ""
    ANTHROPIC_CUSTOM_MODEL_OPTION = $model
    ANTHROPIC_CUSTOM_MODEL_OPTION_NAME = "Claude Sonnet via OpenRouter"
    ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION = "Route Claude Code through OpenRouter to Claude Sonnet"
    ANTHROPIC_DEFAULT_OPUS_MODEL = $model
    ANTHROPIC_DEFAULT_SONNET_MODEL = $model
    ANTHROPIC_DEFAULT_HAIKU_MODEL = $model
    CLAUDE_CODE_SUBAGENT_MODEL = $model
    API_TIMEOUT_MS = $apiTimeout
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = $disableNoise
}

Set-SessionEnv -Variables $sessionEnv

$showConfig = $ClaudeArgs -contains "--show-config"
$forwardArgs = Get-FilteredArgs -Args $ClaudeArgs -ExcludedArg "--show-config"

if ($showConfig) {
    Show-LauncherConfig `
        -EntryName "claude-claude-openrouter" `
        -Model $model `
        -BaseUrl "https://openrouter.ai/api" `
        -AuthSource "runtime env from OPENROUTER_API_KEY" `
        -SettingSources "project,local + launcher overrides" `
        -ClaudePath ((Get-Command claude).Path)
    exit 0
}

Invoke-ClaudeLauncher -Settings $settings -ForwardArgs $forwardArgs

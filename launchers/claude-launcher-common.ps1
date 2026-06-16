Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-JsonProperty {
    param(
        [Parameter(Mandatory = $true)]
        $Object,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if ($null -eq $Object) {
        return $false
    }

    return $Object.PSObject.Properties.Name -contains $Name
}

function Get-JsonProperty {
    param(
        [Parameter(Mandatory = $true)]
        $Object,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if (Test-JsonProperty -Object $Object -Name $Name) {
        return $Object.$Name
    }

    return $null
}

function Get-ClaudeUserSettings {
    $settingsPath = Join-Path $env:USERPROFILE ".claude\settings.json"

    if (-not (Test-Path -LiteralPath $settingsPath)) {
        throw "Claude user settings not found: $settingsPath"
    }

    $settings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json

    return @{
        Path = $settingsPath
        Data = $settings
    }
}

function Get-PreservedClaudeSettings {
    param(
        [Parameter(Mandatory = $true)]
        $UserSettings,
        [Parameter(Mandatory = $true)]
        [string]$Model
    )

    $settings = @{}

    foreach ($key in @(
        "permissions",
        "enabledPlugins",
        "extraKnownMarketplaces",
        "skipDangerousModePermissionPrompt",
        "skipAutoPermissionPrompt"
    )) {
        if (Test-JsonProperty -Object $UserSettings -Name $key) {
            $settings[$key] = Get-JsonProperty -Object $UserSettings -Name $key
        }
    }

    $settings["model"] = $Model

    return $settings
}

function Set-SessionEnv {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$Variables
    )

    foreach ($entry in $Variables.GetEnumerator()) {
        $envName = [string]$entry.Key
        $envValue = $entry.Value

        if ($null -eq $envValue) {
            Remove-Item -Path ("Env:" + $envName) -ErrorAction SilentlyContinue
            continue
        }

        Set-Item -Path ("Env:" + $envName) -Value ([string]$envValue)
    }
}

function Get-FilteredArgs {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args,
        [Parameter(Mandatory = $true)]
        [string]$ExcludedArg
    )

    return @($Args | Where-Object { $_ -ne $ExcludedArg })
}

function Show-LauncherConfig {
    param(
        [Parameter(Mandatory = $true)]
        [string]$EntryName,
        [Parameter(Mandatory = $true)]
        [string]$Model,
        [Parameter(Mandatory = $true)]
        [string]$BaseUrl,
        [Parameter(Mandatory = $true)]
        [string]$AuthSource,
        [Parameter(Mandatory = $true)]
        [string]$SettingSources,
        [Parameter(Mandatory = $true)]
        [string]$ClaudePath
    )

    Write-Host ("entry           : " + $EntryName)
    Write-Host ("model           : " + $Model)
    Write-Host ("base_url        : " + $BaseUrl)
    Write-Host ("auth_source     : " + $AuthSource)
    Write-Host ("setting_sources : " + $SettingSources)
    Write-Host ("claude_path     : " + $ClaudePath)
}

function Invoke-ClaudeLauncher {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$Settings,
        [Parameter(Mandatory = $true)]
        [string[]]$ForwardArgs
    )

    $settingsJson = $Settings | ConvertTo-Json -Depth 20 -Compress
    $runtimeDir = Join-Path $PSScriptRoot ".runtime"
    if (-not (Test-Path -LiteralPath $runtimeDir)) {
        New-Item -ItemType Directory -Path $runtimeDir | Out-Null
    }

    $settingsFile = Join-Path $runtimeDir ("settings-" + [guid]::NewGuid().ToString() + ".json")

    $exitCode = 0

    try {
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($settingsFile, $settingsJson, $utf8NoBom)
        & claude --setting-sources "project,local" --settings $settingsFile @ForwardArgs
        $exitCode = $LASTEXITCODE
    }
    finally {
        if (Test-Path -LiteralPath $settingsFile) {
            Remove-Item -LiteralPath $settingsFile -Force
        }
    }

    exit $exitCode
}

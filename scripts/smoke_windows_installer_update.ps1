param(
    [Parameter(Mandatory = $true)]
    [string]$Installer,
    [Parameter(Mandatory = $true)]
    [string]$LegacyExecutable
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$installerPath = (Resolve-Path -LiteralPath $Installer).Path
$legacyExecutablePath = (Resolve-Path -LiteralPath $LegacyExecutable).Path
$runnerRoot = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { $env:TEMP }
$testRoot = Join-Path $runnerRoot ("cat-type-installer-update-" + [guid]::NewGuid())
$target = Join-Path $testRoot "Legacy Cat Type"
$installedExe = Join-Path $target "Cat Type.exe"
$installerLog = Join-Path $testRoot "installer.log"
New-Item -ItemType Directory -Path $target | Out-Null

$nativeSource = @'
using System;
using System.Runtime.InteropServices;
public static class CatTypeUpdateNative {
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern IntPtr OpenEvent(uint access, bool inherit, string name);
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool SetEvent(IntPtr handle);
    [DllImport("kernel32.dll")]
    public static extern bool CloseHandle(IntPtr handle);
}
'@
Add-Type -TypeDefinition $nativeSource

function Get-TestProcesses {
    @(Get-CimInstance Win32_Process | Where-Object {
        $_.ExecutablePath -and
        [string]::Equals(
            $_.ExecutablePath,
            $installedExe,
            [System.StringComparison]::OrdinalIgnoreCase
        )
    })
}

function Stop-TestProcesses {
    Get-TestProcesses | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
    $deadline = [DateTime]::UtcNow.AddSeconds(10)
    while (@(Get-TestProcesses).Count -and [DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Milliseconds 100
    }
}

function Wait-ForShutdownEvent([int]$Seconds) {
    $deadline = [DateTime]::UtcNow.AddSeconds($Seconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        $handle = [CatTypeUpdateNative]::OpenEvent(
            0x0002,
            $false,
            "Local\CatTypeShutdown"
        )
        if ($handle -ne [IntPtr]::Zero) {
            return $handle
        }
        Start-Sleep -Milliseconds 100
    }
    throw "Updated Cat Type did not create its shutdown event."
}

try {
    Copy-Item -LiteralPath $legacyExecutablePath -Destination $installedExe
    $legacy = Start-Process -FilePath $installedExe -PassThru
    $legacyDeadline = [DateTime]::UtcNow.AddSeconds(30)
    while (@(Get-TestProcesses).Count -lt 2 -and [DateTime]::UtcNow -lt $legacyDeadline) {
        Start-Sleep -Milliseconds 100
    }
    $legacyProcesses = @(Get-TestProcesses)
    if ($legacyProcesses.Count -lt 2) {
        throw "Pinned legacy PyInstaller fixture did not start both processes."
    }
    $legacyProcessIds = @($legacyProcesses | ForEach-Object { $_.ProcessId })
    Start-Sleep -Seconds 5
    $stableLegacyProcesses = @(Get-CimInstance Win32_Process | Where-Object {
        $legacyProcessIds -contains $_.ProcessId
    })
    if ($stableLegacyProcesses.Count -ne $legacyProcessIds.Count) {
        throw "Pinned legacy PyInstaller processes did not remain alive."
    }

    $arguments = @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/CLOSEAPPLICATIONS",
        "/FORCECLOSEAPPLICATIONS",
        "/NORESTART",
        "/CURRENTUSER",
        "/AUTOUPDATE=1",
        "/NOICONS",
        "/TASKS=",
        ('/LOG="' + $installerLog + '"'),
        ('/DIR="' + $target + '"')
    )
    $install = Start-Process `
        -FilePath $installerPath `
        -ArgumentList $arguments `
        -PassThru
    # -Wait includes descendants, but a successful update relaunches Cat Type.
    Wait-Process -InputObject $install -Timeout 60 -ErrorAction Stop
    if ($install.ExitCode -ne 0) {
        throw "Auto-update installer exited with status $($install.ExitCode)."
    }
    $remainingLegacy = @(Get-CimInstance Win32_Process | Where-Object {
        $legacyProcessIds -contains $_.ProcessId
    })
    if ($remainingLegacy.Count) {
        throw "Auto-update installer did not close every legacy PyInstaller process."
    }
    if (-not (Test-Path -LiteralPath $installedExe)) {
        throw "Auto-update installer did not place Cat Type.exe."
    }
    $versionSource = Get-Content -LiteralPath "app_version.py" -Raw
    $versionMatch = [regex]::Match(
        $versionSource,
        'APP_VERSION: str = "([0-9]+\.[0-9]+\.[0-9]+)"'
    )
    if (-not $versionMatch.Success) {
        throw "Could not read APP_VERSION for installer smoke."
    }
    $installedVersion = (Get-Item -LiteralPath $installedExe).VersionInfo.ProductVersion
    if ($installedVersion -ne $versionMatch.Groups[1].Value) {
        throw "Installed version $installedVersion does not match APP_VERSION."
    }

    $handle = Wait-ForShutdownEvent 30
    try {
        if (-not [CatTypeUpdateNative]::SetEvent($handle)) {
            throw "Could not signal the relaunched Cat Type process."
        }
    }
    finally {
        [CatTypeUpdateNative]::CloseHandle($handle) | Out-Null
    }
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    while (@(Get-TestProcesses).Count -and [DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Milliseconds 100
    }
    if (@(Get-TestProcesses).Count) {
        throw "Relaunched Cat Type processes did not exit after shutdown signal."
    }
    Write-Output "Windows legacy installer update smoke passed."
}
catch {
    if (Test-Path -LiteralPath $installerLog) {
        Write-Output "--- isolated installer log ---"
        Get-Content -LiteralPath $installerLog
        Write-Output "--- end isolated installer log ---"
    }
    throw
}
finally {
    Stop-TestProcesses
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Recurse -Force
    }
}

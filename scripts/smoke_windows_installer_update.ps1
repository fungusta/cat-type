param(
    [Parameter(Mandatory = $true)]
    [string]$Installer
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$installerPath = (Resolve-Path -LiteralPath $Installer).Path
$runnerRoot = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { $env:TEMP }
$testRoot = Join-Path $runnerRoot ("cat-type-installer-update-" + [guid]::NewGuid())
$target = Join-Path $testRoot "Legacy Cat Type"
$installedExe = Join-Path $target "Cat Type.exe"
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
    $legacySource = @'
using System;
using System.Threading;
public static class Program {
    [STAThread]
    public static void Main() { Thread.Sleep(Timeout.Infinite); }
}
'@
    Add-Type `
        -TypeDefinition $legacySource `
        -OutputAssembly $installedExe `
        -OutputType WindowsApplication
    $legacy = Start-Process -FilePath $installedExe -PassThru
    Start-Sleep -Milliseconds 500
    if ($legacy.HasExited) {
        throw "Synthetic legacy Cat Type exited before installer handoff."
    }

    $arguments = @(
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/CLOSEAPPLICATIONS",
        "/FORCECLOSEAPPLICATIONS",
        "/NORESTART",
        "/CURRENTUSER",
        "/AUTOUPDATE=1",
        ('/DIR="' + $target + '"')
    )
    $install = Start-Process `
        -FilePath $installerPath `
        -ArgumentList $arguments `
        -Wait `
        -PassThru
    if ($install.ExitCode -ne 0) {
        throw "Auto-update installer exited with status $($install.ExitCode)."
    }
    $legacy.Refresh()
    if (-not $legacy.HasExited) {
        throw "Auto-update installer did not close the legacy process."
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
    while ((Get-TestProcesses).Count -and [DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Milliseconds 100
    }
    if ((Get-TestProcesses).Count) {
        throw "Relaunched Cat Type processes did not exit after shutdown signal."
    }
    Write-Output "Windows legacy installer update smoke passed."
}
finally {
    Stop-TestProcesses
    $uninstaller = Get-ChildItem `
        -LiteralPath $target `
        -Filter "unins*.exe" `
        -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($uninstaller) {
        Start-Process `
            -FilePath $uninstaller.FullName `
            -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" `
            -Wait
    }
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Recurse -Force
    }
}

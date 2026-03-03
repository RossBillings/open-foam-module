#Requires -Version 5.1

# Installs all tools and dependencies required to build if not available already:
# 1. Python 3.12
# 2. pipx
# 3. poetry

# If Python is not available, the target Python version will be installed system-wide. Otherwise, the target version will be installed per user or system-wide, depending on where an existing Python installation is detected
# Assumes a 64-bit system.

$ErrorActionPreference = "Stop"

$PythonVersion = "3.12"
$PythonDownloadVersion = "3.12.7"

function Install-Python {

    param (
        [String]$PythonDownloadVersion
    )

    $PythonDownloadPath = "python-${PythonDownloadVersion}-amd64.exe"
    Write-Host "Downloading Python $PythonDownloadVersion to $PythonDownloadPath."
    Invoke-WebRequest -Uri "https://www.python.org/ftp/python/${PythonDownloadVersion}/python-${PythonDownloadVersion}-amd64.exe" -OutFile $PythonDownloadPath
    Write-Host "Installing Python $PythonDownloadVersion."
    Start-Process -Wait -ArgumentList /quiet $PythonDownloadPath
    Write-Host "Cleaning up $PythonDownloadPath."
    Remove-Item $PythonDownloadPath
}

function Get-Python {
    param (
        [String]$PythonVersion
    )
    Write-Host "Checking if Python $PythonVersion is available."

    $HkcuPythonPath = "HKCU:\SOFTWARE\Python\PythonCore\${PythonVersion}\InstallPath"
    $HklmPythonPath = "HKLM:\SOFTWARE\Python\PythonCore\${PythonVersion}\InstallPath"

    if (!(Get-Command py -errorAction SilentlyContinue) -or !(py -${PythonVersion} -V 2>$null)) {
        Write-Host "Could not use the Python launcher to find Python $PythonVersion. Looking in Windows Registry."
        if (Test-Path $HkcuPythonPath) {
            Write-Host "Found Python $PythonVersion installed for user."
            $PythonPath = (Get-ItemProperty -Path $HkcuPythonPath).ExecutablePath
        }
        elseif (Test-Path $HklmPythonPath) {
            Write-Host "Found Python $PythonVersion installed for machine."
            $PythonPath = (Get-ItemProperty -Path $HklmPythonPath).ExecutablePath
        }
        else {
            Write-Host "Did not find Python $PythonVersion installed per user or machine."
            Install-Python $PythonDownloadVersion
            $PythonPath = (Get-ItemProperty -Path $HkcuPythonPath).ExecutablePath
        }
    }
    else {
        $PythonPath = py -$PythonVersion -c "import sys;print(sys.executable)"
    }
    Write-Host "Using Python at $PythonPath."
    return $PythonPath
}

$PythonPath = Get-Python $PythonVersion

if (!(Get-Command poetry -errorAction SilentlyContinue)) {
    if (!(& $PythonPath -m pipx --version 2>$null)) {
        Write-Host "Installing pipx with $PythonPath."
        & $PythonPath -m pip install --user pipx
    }
    Write-Host "Installing poetry."
    & $PythonPath -m pipx install poetry
    Write-Host "Adding $env:USERPROFILE\.local\bin to PATH. This change will not be reflected outside this script if not sourced."
    $env:PATH = "$env:PATH;$env:USERPROFILE\.local\bin"
}

Write-Host "Installing dependencies."
poetry env use $PythonPath
poetry install

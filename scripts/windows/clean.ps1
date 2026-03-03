#Requires -Version 5.1
$ErrorActionPreference = "Stop"
Write-Host "Removing poetry environment."
poetry env remove $(poetry env info --path | Split-Path -Leaf)
Write-Host "Cleaning up build outputs."
Remove-Item -Recurse build
Remove-Item -Recurse dist

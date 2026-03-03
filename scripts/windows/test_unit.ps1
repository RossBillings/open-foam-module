#Requires -Version 5.1
$ErrorActionPreference = "Stop"

Write-Host "Running Tests"
poetry run pytest . -vv --cov=.

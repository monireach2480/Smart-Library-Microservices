<#
.SYNOPSIS
    Builds the nine Smart Library container images directly inside Minikube's Docker daemon.

.DESCRIPTION
    Minikube runs its own Docker daemon. Images built on the Windows host are invisible to it, which is
    why every Deployment uses `imagePullPolicy: IfNotPresent` together with images built here.

.EXAMPLE
    .\scripts\k8s-build-images.ps1
    .\scripts\k8s-build-images.ps1 -Tag 1.1
#>
[CmdletBinding()]
param(
    [string]$Tag = "1.0",
    [string]$Prefix = "smart-library"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$services = @(
    "gateway", "registration-service", "login-service", "catalog-service",
    "member-service", "inventory-service", "borrowing-service", "fine-service", "review-service"
)

Write-Host "Pointing this shell at Minikube's Docker daemon..." -ForegroundColor Cyan
& minikube -p minikube docker-env --shell powershell | Invoke-Expression
if ($LASTEXITCODE -ne 0) { throw "minikube docker-env failed. Is Minikube running? Try: minikube start" }

foreach ($svc in $services) {
    $context = Join-Path $root "services\$svc"
    $image = "$Prefix/${svc}:$Tag"
    Write-Host "`nBuilding $image" -ForegroundColor Yellow
    docker build -t $image $context
    if ($LASTEXITCODE -ne 0) { throw "docker build failed for $svc" }
}

Write-Host "`nPulling the two helper images used by the sidecar and the log viewer..." -ForegroundColor Cyan
docker pull busybox:1.36
docker pull python:3.12-slim

Write-Host "`nImages now available inside Minikube:" -ForegroundColor Green
docker images --filter "reference=$Prefix/*" --format "  {{.Repository}}:{{.Tag}}  {{.Size}}"

Write-Host "`nNext:  .\scripts\k8s-deploy.ps1" -ForegroundColor Green

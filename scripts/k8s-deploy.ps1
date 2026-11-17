<#
.SYNOPSIS
    Applies every Smart Library manifest to the cluster and waits for the rollout.

.DESCRIPTION
    Uses YAML configuration files only - no imperative `kubectl create deployment`, no Helm.
    Order matters: Namespace, then config/secret/storage, then workloads, then the Ingress.

.EXAMPLE
    .\scripts\k8s-deploy.ps1
    .\scripts\k8s-deploy.ps1 -SkipNetworkPolicy     # if your CNI does not support NetworkPolicy
#>
[CmdletBinding()]
param(
    [switch]$SkipNetworkPolicy,
    [int]$TimeoutSeconds = 300
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$k8s = Join-Path $root "k8s"
$ns = "smart-library"

if (-not (Test-Path (Join-Path $k8s "02-secret.yaml"))) {
    throw "k8s/02-secret.yaml is missing. Create it first:  .\scripts\k8s-make-secret.ps1"
}

Write-Host "=== 1. Namespace ===" -ForegroundColor Cyan
kubectl apply -f (Join-Path $k8s "00-namespace.yaml")

Write-Host "`n=== 2. Config, secrets, shared log volume ===" -ForegroundColor Cyan
kubectl apply -f (Join-Path $k8s "01-configmap.yaml")
kubectl apply -f (Join-Path $k8s "02-secret.yaml")
kubectl apply -f (Join-Path $k8s "03-storage.yaml")

Write-Host "`n=== 3. Microservices, gateway, log viewer ===" -ForegroundColor Cyan
Get-ChildItem -Path $k8s -Filter "*.yaml" |
    Where-Object { $_.Name -match "^(1\d|2\d)-" } |
    Sort-Object Name |
    ForEach-Object { kubectl apply -f $_.FullName }

Write-Host "`n=== 4. Fanout DNS ingress ===" -ForegroundColor Cyan
kubectl apply -f (Join-Path $k8s "30-ingress.yaml")

if (-not $SkipNetworkPolicy) {
    Write-Host "`n=== 5. Network policies (gateway-only access) ===" -ForegroundColor Cyan
    kubectl apply -f (Join-Path $k8s "40-networkpolicy.yaml")
}

Write-Host "`n=== Waiting for rollouts (up to $TimeoutSeconds s each) ===" -ForegroundColor Cyan
$deployments = @(
    "registration-service", "login-service", "catalog-service", "member-service",
    "inventory-service", "borrowing-service", "fine-service", "review-service",
    "gateway", "log-viewer"
)
$failed = @()
foreach ($d in $deployments) {
    kubectl -n $ns rollout status "deployment/$d" --timeout "${TimeoutSeconds}s"
    if ($LASTEXITCODE -ne 0) { $failed += $d }
}

Write-Host "`n=== Cluster state ===" -ForegroundColor Cyan
kubectl -n $ns get pods -o wide
kubectl -n $ns get svc
kubectl -n $ns get ingress
kubectl -n $ns get pvc

if ($failed.Count -gt 0) {
    Write-Host "`nThese deployments did not become ready: $($failed -join ', ')" -ForegroundColor Red
    Write-Host "Most common cause: a wrong DATABASE_URL in k8s/02-secret.yaml. Check with:"
    Write-Host "  kubectl -n $ns logs deploy/$($failed[0])"
    exit 1
}

Write-Host "`nAll deployments ready." -ForegroundColor Green
Write-Host "Verify the rubric requirements:  .\scripts\k8s-verify.ps1" -ForegroundColor Green

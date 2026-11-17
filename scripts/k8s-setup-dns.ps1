<#
.SYNOPSIS
    Points aupp.com, api.aupp.com and logs.aupp.com at the Minikube cluster (fanout DNS, guideline 5).

.DESCRIPTION
    The Ingress routes by Host header, so the browser must send `Host: aupp.com` and the name must
    resolve to the cluster IP. On a local cluster that is done with the Windows hosts file.

    MUST BE RUN FROM AN ELEVATED (Administrator) PowerShell - the hosts file is protected.

.EXAMPLE
    .\scripts\k8s-setup-dns.ps1
    .\scripts\k8s-setup-dns.ps1 -Remove
#>
[CmdletBinding()]
param(
    [string]$ClusterIp,
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$hostsFile = "$env:SystemRoot\System32\drivers\etc\hosts"
$marker = "# smart-library (aupp.com fanout DNS)"
$names = @("aupp.com", "api.aupp.com", "logs.aupp.com")

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
          ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    throw "Run this from an Administrator PowerShell (right-click PowerShell > Run as administrator)."
}

# Drop any previous block so the script is safe to re-run after the cluster IP changes.
$lines = Get-Content $hostsFile | Where-Object { $_ -notmatch [regex]::Escape($marker) }
foreach ($n in $names) {
    $lines = $lines | Where-Object { $_ -notmatch "\s$([regex]::Escape($n))(\s|$)" }
}

if ($Remove) {
    Set-Content -Path $hostsFile -Value $lines -Encoding ASCII
    Write-Host "Removed the aupp.com entries from $hostsFile" -ForegroundColor Green
    ipconfig /flushdns | Out-Null
    return
}

if (-not $ClusterIp) {
    $ClusterIp = (& minikube ip).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $ClusterIp) {
        throw "Could not read the Minikube IP. Start the cluster first: minikube start"
    }
}

$entry = "$ClusterIp`t$($names -join ' ')`t$marker"
Set-Content -Path $hostsFile -Value ($lines + $entry) -Encoding ASCII
ipconfig /flushdns | Out-Null

Write-Host "Added to $hostsFile :" -ForegroundColor Green
Write-Host "  $entry"
Write-Host "`nVerify once the cluster is up:" -ForegroundColor Cyan
Write-Host "  curl.exe http://aupp.com/health"
Write-Host "  curl.exe http://api.aupp.com/api/books"
Write-Host "  curl.exe http://logs.aupp.com/"
Write-Host "`nNOTE for the Docker driver on Windows: `minikube ip` is not reachable directly." -ForegroundColor Yellow
Write-Host "Run `minikube tunnel` in a second Administrator window and use 127.0.0.1 instead:"
Write-Host "  .\scripts\k8s-setup-dns.ps1 -ClusterIp 127.0.0.1"

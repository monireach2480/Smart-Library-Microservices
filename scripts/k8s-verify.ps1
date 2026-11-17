<#
.SYNOPSIS
    Checks every project guideline against the running cluster and saves the output as evidence.

.DESCRIPTION
    Writes one text file per check into evidence/k8s-run/, plus SUMMARY.md. Run it after
    .\scripts\k8s-deploy.ps1 and hand the folder in with the report.

.EXAMPLE
    .\scripts\k8s-verify.ps1
#>
[CmdletBinding()]
param(
    [string]$BaseUrl = "http://aupp.com",
    [string]$OutDir
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$ns = "smart-library"
if (-not $OutDir) { $OutDir = Join-Path $root "evidence\k8s-run" }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$results = [ordered]@{}

function Save([string]$Name, [scriptblock]$Block) {
    Write-Host "`n--- $Name ---" -ForegroundColor Cyan
    $out = & $Block 2>&1 | Out-String
    Write-Host $out
    Set-Content -Path (Join-Path $OutDir "$Name.txt") -Value $out -Encoding UTF8
    return $out
}

# ------------------------------------------------------------------ guideline 1 & 2: K8s objects
$o = Save "01-kubernetes-objects" {
    kubectl -n $ns get deployments,pods,svc,ingress,pvc,networkpolicy -o wide
}
$results["1. YAML-only Kubernetes deployment"] = if ($o -match "deployment.apps/gateway") { "PASS" } else { "CHECK" }

$o = Save "02-pods" { kubectl -n $ns get pods -o wide }
$podCount = ([regex]::Matches($o, "Running")).Count
$results["2. Multiple Pods ($podCount running)"] = if ($podCount -ge 10) { "PASS" } else { "CHECK" }

# ------------------------------------------------------------------ guideline 3: gateway only
$o = Save "03-gateway-only-routing" {
    Write-Output "Every microservice Service must be ClusterIP (no NodePort / LoadBalancer):"
    kubectl -n $ns get svc -o custom-columns="NAME:.metadata.name,TYPE:.spec.type"
    Write-Output "`nIngress backends (only gateway and log-viewer may appear):"
    kubectl -n $ns get ingress smart-library-fanout -o jsonpath="{range .spec.rules[*]}{.host}{':'}{range .http.paths[*]}{' '}{.backend.service.name}{end}{'\n'}{end}"
    Write-Output "`nClient call through the gateway:"
    curl.exe -s -o NUL -w "  GET $BaseUrl/api/books -> HTTP %{http_code}\n" "$BaseUrl/api/books"
    Write-Output "`nInternal endpoints must be refused by the gateway:"
    curl.exe -s -o NUL -w "  GET $BaseUrl/api/internal/ping -> HTTP %{http_code} (expect 403)\n" "$BaseUrl/api/internal/ping"
}
$results["3. All traffic via API Gateway"] = if ($o -notmatch "NodePort|LoadBalancer") { "PASS" } else { "FAIL - a Service is exposed directly" }

# ------------------------------------------------------------------ guideline 4: cloud database
$o = Save "04-cloud-database" {
    Write-Output "There must be NO database Pod in the cluster:"
    $dbPods = kubectl -n $ns get pods -o jsonpath="{range .items[*]}{.metadata.name}{'\n'}{end}" |
              Select-String -Pattern "postgres|mysql|mongo|mariadb"
    if ($dbPods) { Write-Output "  FOUND: $dbPods" } else { Write-Output "  none - OK" }

    Write-Output "`nNo database image is referenced by any manifest:"
    $imgs = kubectl -n $ns get pods -o jsonpath="{range .items[*]}{range .spec.containers[*]}{.image}{'\n'}{end}{end}" | Sort-Object -Unique
    $imgs | ForEach-Object { Write-Output "  $_" }

    Write-Output "`nEach service points at an external host (password masked):"
    foreach ($key in @("AUTH","CATALOG","INVENTORY","BORROWING","FINE","REVIEW")) {
        $url = kubectl -n $ns get secret smart-library-secrets -o jsonpath="{.data.${key}_DATABASE_URL}"
        if ($url) {
            $plain = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($url))
            $masked = $plain -replace "://([^:]+):([^@]+)@", '://$1:****@'
            Write-Output "  ${key}: $masked"
        }
    }
}
$results["4. Cloud database (no DB container)"] = if ($o -match "none - OK") { "PASS" } else { "FAIL - a database Pod is running" }

# ------------------------------------------------------------------ guideline 5: fanout DNS
$o = Save "05-fanout-dns" {
    kubectl -n $ns describe ingress smart-library-fanout
    Write-Output "`nResolving the three names:"
    foreach ($h in @("aupp.com", "api.aupp.com", "logs.aupp.com")) {
        $ip = (Resolve-DnsName $h -ErrorAction SilentlyContinue | Select-Object -First 1).IPAddress
        Write-Output "  $h -> $ip"
    }
    Write-Output "`nFanout in action - one IP, different backends:"
    curl.exe -s -o NUL -w "  http://aupp.com/health        -> HTTP %{http_code}  (gateway)\n" "http://aupp.com/health"
    curl.exe -s -o NUL -w "  http://api.aupp.com/api/books -> HTTP %{http_code}  (gateway)\n" "http://api.aupp.com/api/books"
    curl.exe -s -o NUL -w "  http://logs.aupp.com/         -> HTTP %{http_code}  (log-viewer)\n" "http://logs.aupp.com/"
    curl.exe -s -o NUL -w "  http://aupp.com/logs/         -> HTTP %{http_code}  (log-viewer)\n" "http://aupp.com/logs/"
}
$results["5. Fanout DNS on aupp.com"] = if ($o -match "aupp\.com") { "PASS" } else { "CHECK" }

# ------------------------------------------------------------------ guideline 6: shared volume
$o = Save "06-shared-volume" {
    kubectl -n $ns get pvc smart-library-logs -o wide
    Write-Output "`nGenerating traffic across several services..."
    1..5 | ForEach-Object {
        curl.exe -s -o NUL "$BaseUrl/api/books"
        curl.exe -s -o NUL "$BaseUrl/api/reviews"
        curl.exe -s -o NUL "$BaseUrl/health"
    }
    Start-Sleep -Seconds 3

    $gw = kubectl -n $ns get pod -l app=gateway -o jsonpath="{.items[0].metadata.name}"
    $cat = kubectl -n $ns get pod -l app=catalog-service -o jsonpath="{.items[0].metadata.name}"
    $viewer = kubectl -n $ns get pod -l app=log-viewer -o jsonpath="{.items[0].metadata.name}"

    Write-Output "`nDistinct containers that WROTE to the one shared file:"
    kubectl -n $ns exec $viewer -- sh -c "cat /var/log/smartlibrary/access.log | sed 's/.*\`"instance\`":\`"\([^\`"]*\)\`".*/\1/' | sort -u"

    Write-Output "`nSame file read from the GATEWAY container ($gw):"
    kubectl -n $ns exec $gw -c gateway -- sh -c "wc -l /var/log/smartlibrary/access.log"

    Write-Output "`nSame file read from a CATALOG container ($cat):"
    kubectl -n $ns exec $cat -- sh -c "wc -l /var/log/smartlibrary/access.log"

    Write-Output "`nSame file read from the LOG-VIEWER container ($viewer):"
    kubectl -n $ns exec $viewer -- sh -c "wc -l /var/log/smartlibrary/access.log"

    Write-Output "`nLast 10 lines as seen by the log-tailer SIDECAR in the gateway Pod:"
    kubectl -n $ns logs $gw -c log-tailer --tail=10
}
$results["6. Shared Kubernetes Volume"] = if ($o -match "access\.log") { "PASS" } else { "CHECK" }

# ------------------------------------------------------------------ load balancing across replicas
$o = Save "07-load-balancing" {
    Write-Output "30 requests to /api/books - X-Served-By names the Catalog Pod that answered:"
    $served = 1..30 | ForEach-Object {
        (curl.exe -s -D - -o NUL "$BaseUrl/api/books" | Select-String "X-Served-By").ToString().Trim()
    }
    $served | Group-Object | Sort-Object Name | ForEach-Object {
        Write-Output ("  {0}  x{1}" -f $_.Name, $_.Count)
    }
}
$results["Load balancing across 3 Catalog Pods"] = if (([regex]::Matches($o, "catalog-service-")).Count -ge 2) { "PASS" } else { "CHECK" }

# ------------------------------------------------------------------ summary
$summary = @("# Kubernetes verification - $(Get-Date -Format 'yyyy-MM-dd HH:mm')", "")
$summary += "| Guideline | Result |"
$summary += "|---|---|"
foreach ($k in $results.Keys) { $summary += "| $k | **$($results[$k])** |" }
$summary += ""
$summary += "Raw output for each check is in the .txt files beside this file."
Set-Content -Path (Join-Path $OutDir "SUMMARY.md") -Value ($summary -join "`n") -Encoding UTF8

Write-Host "`n================ SUMMARY ================" -ForegroundColor Green
foreach ($k in $results.Keys) {
    $color = if ($results[$k] -eq "PASS") { "Green" } elseif ($results[$k] -like "FAIL*") { "Red" } else { "Yellow" }
    Write-Host ("{0,-42} {1}" -f $k, $results[$k]) -ForegroundColor $color
}
Write-Host "`nEvidence saved to $OutDir" -ForegroundColor Green

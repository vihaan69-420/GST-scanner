# Live Invoice Processing Monitor
# Watch this while you upload invoices to see real-time results

$LogPath = "C:\Users\clawd bot\Documents\GST-scanner\logs\gst_scanner.log"
$MetricsUrl = "http://localhost:8080/metrics"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "📊 GST Scanner - Live Processing Monitor" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "📝 Monitoring: $LogPath" -ForegroundColor Yellow
Write-Host "🌐 Dashboard: http://localhost:8080/dashboard" -ForegroundColor Yellow
Write-Host "`nPress Ctrl+C to stop monitoring`n" -ForegroundColor Gray
Write-Host "----------------------------------------`n" -ForegroundColor Gray

# Show current metrics before starting
try {
    $metrics = Invoke-RestMethod -Uri $MetricsUrl -TimeoutSec 5
    Write-Host "📊 Current Stats:" -ForegroundColor Green
    Write-Host "   ✓ Total Invoices: $($metrics.invoices.total)" -ForegroundColor White
    Write-Host "   ✓ Success: $($metrics.invoices.success) | Failed: $($metrics.invoices.failed)" -ForegroundColor White
    Write-Host "   ✓ API Calls - OCR: $($metrics.api_calls.ocr.count) | Parsing: $($metrics.api_calls.parsing.count)" -ForegroundColor White
    Write-Host "   💰 Total Cost: `$$([math]::Round($metrics.api_calls.total_cost_usd, 4))" -ForegroundColor White
    Write-Host "`n----------------------------------------`n" -ForegroundColor Gray
}
catch {
    Write-Host "⚠ Could not fetch initial metrics" -ForegroundColor Yellow
}

# Watch logs with color-coded output
Get-Content $LogPath -Wait -Tail 0 | ForEach-Object {
    $line = $_
    
    # Color code based on log level and content
    if ($line -match '\[ERROR\]') {
        Write-Host $line -ForegroundColor Red
    }
    elseif ($line -match '\[WARNING\]') {
        Write-Host $line -ForegroundColor Yellow
    }
    elseif ($line -match 'Started processing') {
        Write-Host "`n$line" -ForegroundColor Cyan
    }
    elseif ($line -match 'Invoice processing complete') {
        Write-Host "$line`n" -ForegroundColor Green
        
        # Fetch and display updated metrics
        try {
            $metrics = Invoke-RestMethod -Uri $MetricsUrl -TimeoutSec 2
            Write-Host "   📊 Updated Stats: Total=$($metrics.invoices.total) Success=$($metrics.invoices.success) Cost=`$$([math]::Round($metrics.api_calls.total_cost_usd, 4))" -ForegroundColor Green
        }
        catch {
            # Ignore
        }
    }
    elseif ($line -match 'Starting OCR') {
        Write-Host "   🔍 $line" -ForegroundColor Magenta
    }
    elseif ($line -match 'OCR complete') {
        Write-Host "   ✓ $line" -ForegroundColor Green
    }
    elseif ($line -match 'Starting parsing') {
        Write-Host "   🔄 $line" -ForegroundColor Blue
    }
    elseif ($line -match 'Parsing complete') {
        Write-Host "   ✓ $line" -ForegroundColor Green
    }
    elseif ($line -match 'Saving to Google Sheets') {
        Write-Host "   💾 $line" -ForegroundColor Yellow
    }
    else {
        Write-Host $line -ForegroundColor Gray
    }
}

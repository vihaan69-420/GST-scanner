# Test Summary Report
# Run this after testing to get a summary of results

$LogPath = "C:\Users\clawd bot\Documents\GST-scanner\logs\gst_scanner.log"
$MetricsUrl = "http://localhost:8080/metrics"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "📋 GST Scanner - Test Summary Report" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Get metrics from API
try {
    $metrics = Invoke-RestMethod -Uri $MetricsUrl -TimeoutSec 5
    
    Write-Host "📊 Overall Statistics:" -ForegroundColor Green
    Write-Host "   Uptime: $([math]::Round($metrics.uptime_seconds / 60, 1)) minutes" -ForegroundColor White
    Write-Host ""
    
    Write-Host "📄 Invoice Processing:" -ForegroundColor Green
    Write-Host "   Total Processed: $($metrics.invoices.total)" -ForegroundColor White
    Write-Host "   ✓ Successful: $($metrics.invoices.success)" -ForegroundColor Green
    Write-Host "   ✗ Failed: $($metrics.invoices.failed)" -ForegroundColor $(if($metrics.invoices.failed -gt 0){'Red'}else{'White'})
    Write-Host "   Today: $($metrics.invoices.today)" -ForegroundColor White
    Write-Host "   Last 24h: $($metrics.invoices.last_24h)" -ForegroundColor White
    Write-Host ""
    
    Write-Host "🔌 API Usage:" -ForegroundColor Green
    Write-Host "   OCR Calls: $($metrics.api_calls.ocr.count)" -ForegroundColor White
    Write-Host "   OCR Tokens: $($metrics.api_calls.ocr.estimated_tokens) (~`$$([math]::Round($metrics.api_calls.ocr.estimated_cost_usd, 4)))" -ForegroundColor White
    Write-Host "   Parsing Calls: $($metrics.api_calls.parsing.count)" -ForegroundColor White
    Write-Host "   Parsing Tokens: $($metrics.api_calls.parsing.estimated_tokens) (~`$$([math]::Round($metrics.api_calls.parsing.estimated_cost_usd, 4)))" -ForegroundColor White
    Write-Host "   💰 Total Cost: `$$([math]::Round($metrics.api_calls.total_cost_usd, 4))" -ForegroundColor Yellow
    Write-Host ""
    
    Write-Host "⚡ Performance:" -ForegroundColor Green
    Write-Host "   Avg Processing Time: $([math]::Round($metrics.performance.avg_processing_time_seconds, 2))s" -ForegroundColor White
    Write-Host "   Min Time: $([math]::Round($metrics.performance.min_processing_time_seconds, 2))s" -ForegroundColor White
    Write-Host "   Max Time: $([math]::Round($metrics.performance.max_processing_time_seconds, 2))s" -ForegroundColor White
    Write-Host "   Active Sessions: $($metrics.performance.active_sessions)" -ForegroundColor White
    Write-Host ""
    
    Write-Host "⚠ Errors:" -ForegroundColor $(if($metrics.errors.total -gt 0){'Red'}else{'Green'})
    Write-Host "   Total Errors: $($metrics.errors.total)" -ForegroundColor $(if($metrics.errors.total -gt 0){'Red'}else{'White'})
    if ($metrics.errors.total -gt 0) {
        Write-Host "   By Type:" -ForegroundColor White
        $metrics.errors.by_type.PSObject.Properties | ForEach-Object {
            Write-Host "      - $($_.Name): $($_.Value)" -ForegroundColor Yellow
        }
    }
    Write-Host ""
    
    Write-Host "🔗 Integrations:" -ForegroundColor Green
    Write-Host "   Telegram: $(if($metrics.integrations.telegram_connected){'✓ Connected'}else{'✗ Disconnected'})" -ForegroundColor $(if($metrics.integrations.telegram_connected){'Green'}else{'Red'})
    Write-Host "   Google Sheets: $(if($metrics.integrations.sheets_accessible){'✓ Accessible'}else{'✗ Not Accessible'})" -ForegroundColor $(if($metrics.integrations.sheets_accessible){'Green'}else{'Red'})
    Write-Host "   Gemini API: $(if($metrics.integrations.gemini_api_available){'✓ Available'}else{'✗ Unavailable'})" -ForegroundColor $(if($metrics.integrations.gemini_api_available){'Green'}else{'Red'})
    
} catch {
    Write-Host "❌ Could not fetch metrics: $_" -ForegroundColor Red
    Write-Host "Is the bot running? Check http://localhost:8080/health" -ForegroundColor Yellow
    exit 1
}

# Get recent processed invoices from logs
Write-Host "`n----------------------------------------`n" -ForegroundColor Gray
Write-Host "📝 Recent Invoices (Last 10):" -ForegroundColor Green

$recentInvoices = Select-String -Path $LogPath -Pattern "Invoice processing (complete|failed)" | Select-Object -Last 10

if ($recentInvoices) {
    foreach ($invoice in $recentInvoices) {
        $line = $invoice.Line
        if ($line -match "processing complete") {
            Write-Host "   ✓ $line" -ForegroundColor Green
        } else {
            Write-Host "   ✗ $line" -ForegroundColor Red
        }
    }
} else {
    Write-Host "   No invoices processed yet" -ForegroundColor Gray
}

# Check for recent errors
Write-Host "`n----------------------------------------`n" -ForegroundColor Gray
Write-Host "⚠ Recent Errors (Last 5):" -ForegroundColor Yellow

$recentErrors = Select-String -Path $LogPath -Pattern "\[ERROR\]" | Select-Object -Last 5

if ($recentErrors) {
    foreach ($error in $recentErrors) {
        Write-Host "   $($error.Line)" -ForegroundColor Red
    }
} else {
    Write-Host "   ✓ No errors found!" -ForegroundColor Green
}

Write-Host "`n========================================`n" -ForegroundColor Cyan

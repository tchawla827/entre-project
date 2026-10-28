$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$deckPath = Join-Path $projectRoot 'Fisheries_Cold_Chain_Project.pptx'
$pdfPath = Join-Path $projectRoot 'Fisheries_Cold_Chain_Project.pdf'
$previewPath = Join-Path $PSScriptRoot 'preview'
New-Item -ItemType Directory -Force -Path $previewPath | Out-Null
$powerPoint = $null
$deck = $null
try {
    $powerPoint = New-Object -ComObject PowerPoint.Application
    $deck = $powerPoint.Presentations.Open($deckPath, $true, $false, $false)
    $deck.SaveAs($pdfPath, 32)
    $deck.Export($previewPath, 'PNG', 1600, 900)
    $overflow = @()
    foreach ($slideCheck in $deck.Slides) {
        foreach ($shapeCheck in $slideCheck.Shapes) {
            if ($shapeCheck.HasTextFrame -and $shapeCheck.TextFrame2.HasText) {
                if ($shapeCheck.TextFrame2.TextRange.BoundHeight -gt ($shapeCheck.Height + 2)) {
                    $overflow += "Slide $($slideCheck.SlideIndex): $($shapeCheck.Name)"
                }
            }
        }
    }
    @{
        rendered_slides = $deck.Slides.Count
        renderer = 'Microsoft PowerPoint'
        text_overflow = $overflow
        pdf = 'Fisheries_Cold_Chain_Project.pdf'
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'render_verification.json') -Encoding UTF8
    if ($overflow.Count -gt 0) { throw "Text overflow: $($overflow -join ', ')" }
    Write-Output "Rendered $($deck.Slides.Count) slides to PDF and PNG."
}
finally {
    if ($null -ne $deck) {
        $deck.Close()
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($deck)
    }
    if ($null -ne $powerPoint) {
        $powerPoint.Quit()
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($powerPoint)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

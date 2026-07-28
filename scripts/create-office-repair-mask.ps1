param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

Add-Type -AssemblyName System.Drawing

$source = [System.Drawing.Image]::FromFile($InputPath)
$mask = New-Object System.Drawing.Bitmap($source.Width, $source.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$graphics = [System.Drawing.Graphics]::FromImage($mask)
$graphics.Clear([System.Drawing.Color]::FromArgb(255, 0, 0, 0))
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$editableBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(0, 0, 0, 0))

$graphics.FillRectangle($editableBrush, 1390, 14, 146, 86)

$chairAreas = @(
    @(238, 409, 48, 69),
    @(619, 408, 48, 71),
    @(962, 408, 49, 71),
    @(237, 812, 49, 72),
    @(619, 810, 49, 74)
)

foreach ($area in $chairAreas) {
    $graphics.FillEllipse($editableBrush, $area[0], $area[1], $area[2], $area[3])
}

$outputDirectory = Split-Path -Parent $OutputPath
if ($outputDirectory) {
    New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
}

$mask.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Png)
$editableBrush.Dispose()
$graphics.Dispose()
$mask.Dispose()
$source.Dispose()

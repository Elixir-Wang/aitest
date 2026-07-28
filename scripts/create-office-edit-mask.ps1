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

$graphics.FillRectangle($editableBrush, 700, 10, 231, 58)

$chairAreas = @(
    @(48, 198, 30, 39), @(139, 196, 31, 40), @(44, 287, 31, 38), @(140, 255, 31, 42),
    @(268, 196, 31, 42), @(371, 194, 32, 41), @(267, 289, 32, 39), @(373, 255, 32, 42),
    @(480, 197, 31, 41), @(575, 196, 34, 40), @(480, 289, 33, 39), @(578, 255, 33, 41),
    @(41, 443, 33, 39), @(138, 443, 34, 39), @(41, 543, 34, 40), @(140, 513, 33, 45),
    @(265, 443, 34, 39), @(365, 443, 33, 40), @(266, 543, 33, 40), @(367, 513, 33, 45)
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

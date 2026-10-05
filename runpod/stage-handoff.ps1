param(
  [string]$HandoffZip = (Join-Path $PSScriptRoot '..\..\accepted-core-app-handoff-v1-20261005.zip')
)
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $HandoffZip).Path
$targetDir = Join-Path $PSScriptRoot 'vendor'
New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
$target = Join-Path $targetDir 'accepted-core-app-handoff-v1-20261005.zip'
Copy-Item -LiteralPath $source -Destination $target -Force
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead($target)
try {
  $entry = $archive.GetEntry('model/accepted-core-52a178b6d3d5.pt')
  if (-not $entry) { throw 'Accepted checkpoint is missing from the handoff ZIP.' }
  $stream = $entry.Open()
  try {
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    try { $modelHash = [BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $hasher.Dispose() }
  } finally { $stream.Dispose() }
  if ($modelHash -ne '52a178b6d3d5d13dac0bd1940fdc81a0dc9ab32a2aa60e9427ea4054d1a2f515') {
    throw 'Accepted checkpoint SHA256 does not match the handoff identity.'
  }
} finally { $archive.Dispose() }
Write-Output "Staged handoff ZIP: $target"
Write-Output "Archive SHA256: $((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant())"
Write-Output "Checkpoint SHA256 verified: $modelHash"

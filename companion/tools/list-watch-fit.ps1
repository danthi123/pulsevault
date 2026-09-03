<#
  list-watch-fit.ps1 — enumerate every .fit file on a USB-connected Garmin watch
  (MTP), with full path, size and modified date, plus a per-folder summary.

  A Garmin watch shows up under "This PC" as an MTP device (no drive letter), so
  we drive Explorer's Shell.Application COM instead of using Get-ChildItem.

  Usage:
    powershell -ExecutionPolicy Bypass -File .\list-watch-fit.ps1
    powershell -ExecutionPolicy Bypass -File .\list-watch-fit.ps1 -CopyTo C:\pv\FIT -Folders MONITOR,SLEEP
#>
param(
  [string]$DeviceMatch = 'fenix|epix|forerunner|instinct|venu|enduro|marq|descent|vivoactive|d2|tactix|garmin',
  [string]$CopyTo,                             # if set, copy matching .fit here
  [string[]]$Folders = @('ACTIVITY','MONITOR','SLEEP','METRICS')  # which GARMIN subfolders to copy from
)

$ErrorActionPreference = 'Stop'
$shell = New-Object -ComObject Shell.Application

function Find-GarminFolder {
  $pc = $shell.Namespace(0x11)               # 0x11 = "This PC"
  foreach ($dev in $pc.Items()) {
    if ($dev.Name -notmatch $DeviceMatch) { continue }
    foreach ($storage in $dev.GetFolder.Items()) {   # Internal Storage / SD card
      $g = $storage.GetFolder.ParseName('GARMIN')
      if ($g) { return [pscustomobject]@{ Device=$dev.Name; Storage=$storage.Name; Garmin=$g.GetFolder } }
    }
  }
  return $null
}

# Recursively walk an MTP folder, emitting every .fit as an object.
function Get-Fit($folder, $prefix) {
  foreach ($item in $folder.Items()) {
    if ($item.IsFolder) {
      Get-Fit $item.GetFolder "$prefix\$($item.Name)"
    } elseif ($item.Name -match '\.fit$') {
      [pscustomobject]@{
        Folder   = $prefix
        Name     = $item.Name
        Size     = [int64]$item.ExtendedProperty('System.Size')
        Modified = $item.ExtendedProperty('System.DateModified')
        _item    = $item
      }
    }
  }
}

$root = Find-GarminFolder
if (-not $root) { Write-Error "No Garmin watch found under 'This PC'. Is it plugged in and unlocked?"; exit 1 }
Write-Host "Watch: $($root.Device)  [$($root.Storage)]`n" -ForegroundColor Cyan

$all = Get-Fit $root.Garmin 'GARMIN'

Write-Host "Per-folder summary:" -ForegroundColor Cyan
$all | Group-Object Folder | Sort-Object Name | ForEach-Object {
  $mb = [math]::Round(($_.Group | Measure-Object Size -Sum).Sum / 1MB, 1)
  "{0,-24} {1,4} files  {2,7} MB" -f $_.Name, $_.Count, $mb
}
Write-Host ("`nTotal: {0} .fit files`n" -f $all.Count) -ForegroundColor Cyan

# Full listing (path, size, modified) — this is your "all paths where .fit files are"
$all | Sort-Object Folder, Name |
  Select-Object Folder, Name, @{n='SizeKB';e={[math]::Round($_.Size/1KB,1)}}, Modified |
  Format-Table -AutoSize

if ($CopyTo) {
  New-Item -ItemType Directory -Force -Path $CopyTo | Out-Null
  $dest = $shell.Namespace($CopyTo)
  $want = $all | Where-Object { ($_.Folder -split '\\')[-1] -in $Folders }
  Write-Host ("`nCopying {0} files from [{1}] to {2} ..." -f $want.Count, ($Folders -join ','), $CopyTo) -ForegroundColor Yellow
  foreach ($f in $want) {
    if (-not (Test-Path (Join-Path $CopyTo $f.Name))) {
      $dest.CopyHere($f._item, 20)           # 4 = no progress UI, 16 = yes-to-all
    }
  }
  Start-Sleep -Seconds 2
  Write-Host ("Done. {0} .fit now in {1}" -f (Get-ChildItem $CopyTo -Filter *.fit).Count, $CopyTo) -ForegroundColor Green
}

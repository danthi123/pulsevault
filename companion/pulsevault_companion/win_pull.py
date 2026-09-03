"""EXPERIMENTAL Windows watch puller.

Windows exposes a Garmin watch over MTP as a shell namespace ("This PC\\fenix...")
rather than a drive, so we drive Explorer's COM (Shell.Application) via PowerShell
to copy new GARMIN\\{Activity,Monitor,Sleep,Metrics}\\*.fit into the inbox. This
is finicky (MTP CopyHere is async and dialog-happy); if it misbehaves, the inbox
still works — just copy files into the FIT folder manually in Explorer.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path

from .state import State

log = logging.getLogger("pulsevault.pull.win")

_PS = r"""
param([Parameter(Mandatory=$true)][string]$Dest,
      [Parameter(Mandatory=$true)][string]$SkipFile)
$ErrorActionPreference = "SilentlyContinue"
$skip = @{}
if (Test-Path $SkipFile) { Get-Content $SkipFile | ForEach-Object { if ($_ -ne "") { $skip[$_] = $true } } }
$shell = New-Object -ComObject Shell.Application
$destNs = $shell.Namespace($Dest)
$pc = $shell.Namespace(0x11)   # This PC
$rx = 'garmin|fenix|epix|forerunner|instinct|venu|enduro|marq|descent|vivoactive|d2|tactix'
foreach ($dev in $pc.Items()) {
  if ($dev.Name -notmatch $rx) { continue }
  foreach ($storage in $dev.GetFolder.Items()) {          # Internal Storage / card
    $garmin = $storage.GetFolder.ParseName("GARMIN")
    if (-not $garmin) { continue }
    foreach ($subName in @("Activity","Monitor","Sleep","Metrics")) {
      $sub = $garmin.GetFolder.ParseName($subName)
      if (-not $sub) { continue }
      foreach ($item in $sub.GetFolder.Items()) {
        if ($item.Name -notmatch '\.fit$') { continue }
        if ($skip.ContainsKey($item.Name)) { continue }
        $destNs.CopyHere($item, 20)     # 4=no progress + 16=yes-to-all
        Start-Sleep -Milliseconds 250
        if (Test-Path (Join-Path $Dest $item.Name)) { Write-Output $item.Name }
      }
    }
  }
}
"""


class WindowsPuller:
    name = "wpd"

    def available(self) -> bool:
        return os.name == "nt"

    def copy_new(self, dest: Path, state: State) -> int:
        skip = [k.split("/", 1)[1] for k in state.keys() if k.startswith("win/")]
        ps_path = skip_path = None
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False) as f:
                f.write(_PS)
                ps_path = f.name
            with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
                f.write("\n".join(skip))
                skip_path = f.name
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", ps_path, "-Dest", str(dest), "-SkipFile", skip_path],
                capture_output=True, text=True, timeout=600,
            )
            if proc.returncode != 0:
                log.warning("windows pull error: %s", (proc.stderr or "")[:300])
            copied = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip().lower().endswith(".fit")]
            for name in copied:
                state.mark("win/" + name, 1)
                log.info("pulled %s", name)
            return len(copied)
        except Exception as exc:  # noqa: BLE001
            log.warning("windows pull failed: %s", exc)
            return 0
        finally:
            for p in (ps_path, skip_path):
                if p:
                    try:
                        os.unlink(p)
                    except OSError:
                        pass

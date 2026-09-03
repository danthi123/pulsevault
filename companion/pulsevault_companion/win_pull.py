"""EXPERIMENTAL Windows watch puller.

Windows exposes a Garmin watch over MTP as a shell namespace ("This PC\\fenix...")
rather than a drive, so we drive Explorer's COM (Shell.Application) via PowerShell
to copy new GARMIN\\{Activity,Monitor,Sleep,Metrics}\\*.fit into the inbox.

The tricky part: Shell.CopyHere is ASYNCHRONOUS. Early versions issued the copy,
slept 250ms, then exited — which aborts the in-flight MTP transfer, so nothing
landed. This version issues each copy and then WAITS (polling the destination for
the file to appear and its size to stabilise) before moving on, keeping the
process alive until the transfers actually finish.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path

from .state import State

log = logging.getLogger("pulsevault.pull.win")

# Emits machine-readable lines:
#   DEV:<name>            a matching device was found
#   FOUND:<folder>:<n>    n .fit files seen in a GARMIN subfolder
#   OK:<name>             file copied + verified into the inbox
#   TIMEOUT:<name>        copy issued but file never finished
#   SKIP:<name>           already in inbox / skip list
_PS = r"""
param([Parameter(Mandatory=$true)][string]$Dest,
      [Parameter(Mandatory=$true)][string]$SkipFile,
      [int]$WaitSec = 25)
$ErrorActionPreference = "SilentlyContinue"

$skip = @{}
if (Test-Path $SkipFile) { Get-Content $SkipFile | ForEach-Object { if ($_ -ne "") { $skip[$_] = $true } } }

$shell = New-Object -ComObject Shell.Application
$destNs = $shell.Namespace($Dest)
if (-not $destNs) { Write-Output "ERR:no-dest"; exit 0 }

$pc = $shell.Namespace(0x11)   # This PC
$rx = 'garmin|fenix|epix|forerunner|instinct|venu|enduro|marq|descent|vivoactive|d2|tactix|approach'
$subFolders = @("Activity","Monitor","Sleep","Metrics")

function Wait-ForFile($dir, $name, $sec) {
  $path = Join-Path $dir $name
  $last = -1
  for ($i = 0; $i -lt ($sec * 4); $i++) {
    if (Test-Path $path) {
      $len = (Get-Item $path).Length
      if ($len -gt 0 -and $len -eq $last) { return $true }  # size stable => done
      $last = $len
    }
    Start-Sleep -Milliseconds 250
  }
  return (Test-Path $path)
}

foreach ($dev in $pc.Items()) {
  if ($dev.Name -notmatch $rx) { continue }
  Write-Output ("DEV:" + $dev.Name)
  foreach ($storage in $dev.GetFolder.Items()) {          # Internal Storage / card
    $garmin = $storage.GetFolder.ParseName("GARMIN")
    if (-not $garmin) { continue }
    foreach ($subName in $subFolders) {
      $sub = $garmin.GetFolder.ParseName($subName)
      if (-not $sub) { continue }
      $items = @($sub.GetFolder.Items() | Where-Object { $_.Name -match '\.fit$' })
      Write-Output ("FOUND:" + $subName + ":" + $items.Count)
      foreach ($item in $items) {
        if ($skip.ContainsKey($item.Name)) { Write-Output ("SKIP:" + $item.Name); continue }
        if (Test-Path (Join-Path $Dest $item.Name)) { Write-Output ("SKIP:" + $item.Name); continue }
        $destNs.CopyHere($item, 20)     # 4 = no progress UI + 16 = yes-to-all
        if (Wait-ForFile $Dest $item.Name $WaitSec) { Write-Output ("OK:" + $item.Name) }
        else { Write-Output ("TIMEOUT:" + $item.Name) }
      }
    }
  }
}
"""


def _run_ps(args: list[str], timeout: int) -> subprocess.CompletedProcess:
    ps_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False) as f:
            f.write(_PS)
            ps_path = f.name
        return subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_path, *args],
            capture_output=True, text=True, timeout=timeout,
        )
    finally:
        if ps_path:
            try:
                os.unlink(ps_path)
            except OSError:
                pass


class WindowsPuller:
    name = "wpd"

    def available(self) -> bool:
        # os-level gate; the actual "is a watch plugged in" check is reported by
        # copy_new()/probe() via the DEV: lines (an MTP scan is too slow to run
        # on every status poll cheaply, but probe() exposes it on demand).
        return os.name == "nt"

    def probe(self):
        """Return a short human summary of what the puller can see right now."""
        empty = Path(tempfile.gettempdir()) / "pv_empty_skip.txt"
        try:
            empty.write_text("")
            proc = _run_ps([str(Path(tempfile.gettempdir())), str(empty), "0"], timeout=60)
        except Exception as exc:  # noqa: BLE001
            return f"probe error: {exc}"
        devs = [ln[4:] for ln in proc.stdout.splitlines() if ln.startswith("DEV:")]
        found = [ln[6:] for ln in proc.stdout.splitlines() if ln.startswith("FOUND:")]
        if not devs:
            return "no Garmin device detected over USB"
        return f"watch(es): {', '.join(devs)}; folders: {', '.join(found) or 'none'}"

    def copy_new(self, dest: Path, state: State) -> int:
        skip = [k.split("/", 1)[1] for k in state.keys() if k.startswith("win/")]
        skip_path = None
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
                f.write("\n".join(skip))
                skip_path = f.name
            proc = _run_ps([str(dest), skip_path, "25"], timeout=900)
        except Exception as exc:  # noqa: BLE001
            log.warning("windows pull failed: %s", exc)
            return 0
        finally:
            if skip_path:
                try:
                    os.unlink(skip_path)
                except OSError:
                    pass

        out = proc.stdout or ""
        devs = [ln[4:] for ln in out.splitlines() if ln.startswith("DEV:")]
        copied = [ln[3:] for ln in out.splitlines() if ln.startswith("OK:")]
        timeouts = [ln[8:] for ln in out.splitlines() if ln.startswith("TIMEOUT:")]
        if not devs:
            log.info("auto-pull: no Garmin device detected over USB")
        else:
            log.info("auto-pull: device(s) %s — copied %d, timed out %d",
                     ", ".join(devs), len(copied), len(timeouts))
        if timeouts:
            log.warning("auto-pull: %d file(s) didn't finish copying (MTP slow/busy): %s",
                        len(timeouts), ", ".join(timeouts[:5]))
        if proc.returncode != 0 and (proc.stderr or "").strip():
            log.debug("windows pull stderr: %s", (proc.stderr or "")[:300])
        for name in copied:
            state.mark("win/" + name, 1)
            log.info("pulled %s", name)
        return len(copied)

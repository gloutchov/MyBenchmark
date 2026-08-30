"""Dependency-free host and per-task system metric collection."""

from __future__ import annotations

import ctypes
import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:  # unavailable on Windows
    import resource
except ImportError:  # pragma: no cover - exercised on Windows CI
    resource = None  # type: ignore[assignment]


def _total_memory_bytes() -> int | None:
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.ullTotalPhys)
        return None
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
    except (AttributeError, OSError, ValueError):
        return None
    return int(pages * page_size) if pages > 0 and page_size > 0 else None


def _rapl_paths() -> tuple[Path, ...]:
    root = Path("/sys/class/powercap")
    if not root.is_dir():
        return ()
    paths = []
    for path in sorted(root.glob("intel-rapl*/energy_uj")):
        try:
            int(path.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            continue
        paths.append(path)
    return tuple(paths)


def hardware_snapshot() -> dict[str, Any]:
    rapl = _rapl_paths()
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "logical_cpu_count": os.cpu_count(),
        "memory_total_bytes": _total_memory_bytes(),
        "energy": {
            "provider": "linux-rapl" if rapl else None,
            "available": bool(rapl),
            "scope": "host" if rapl else None,
            "detail": "Contatori RAPL host-wide" if rapl else "nessun contatore energetico leggibile senza privilegi",
        },
    }


def _rusage_snapshot() -> dict[str, float] | None:
    if resource is None:
        return None
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {
        "user_seconds": float(usage.ru_utime),
        "system_seconds": float(usage.ru_stime),
        "minor_page_faults": float(usage.ru_minflt),
        "major_page_faults": float(usage.ru_majflt),
        "block_inputs": float(usage.ru_inblock),
        "block_outputs": float(usage.ru_oublock),
        "voluntary_context_switches": float(usage.ru_nvcsw),
        "involuntary_context_switches": float(usage.ru_nivcsw),
    }


def _energy_snapshot(paths: tuple[Path, ...]) -> dict[Path, tuple[int, int | None]]:
    values: dict[Path, tuple[int, int | None]] = {}
    for path in paths:
        try:
            current = int(path.read_text(encoding="ascii").strip())
            maximum_path = path.with_name("max_energy_range_uj")
            maximum = int(maximum_path.read_text(encoding="ascii").strip()) if maximum_path.is_file() else None
        except (OSError, ValueError):
            continue
        values[path] = (current, maximum)
    return values


def _load_average() -> list[float] | None:
    try:
        return [round(float(value), 3) for value in os.getloadavg()]
    except (AttributeError, OSError):
        return None


@dataclass
class SystemMetricCollector:
    rusage_before: dict[str, float] | None
    energy_before: dict[Path, tuple[int, int | None]]
    load_before: list[float] | None

    @classmethod
    def start(cls) -> "SystemMetricCollector":
        paths = _rapl_paths()
        return cls(_rusage_snapshot(), _energy_snapshot(paths), _load_average())

    def finish(self) -> dict[str, Any]:
        after = _rusage_snapshot()
        process: dict[str, Any]
        if self.rusage_before is None or after is None:
            process = {
                "available": False,
                "provider": None,
                "detail": "metriche rusage dei processi figli non disponibili",
            }
        else:
            process = {
                "available": True,
                "provider": "posix-rusage-children",
                "scope": "figli terminati osservati dal runner; i discendenti possono non essere completi",
                **{
                    key: round(after[key] - value, 6)
                    for key, value in self.rusage_before.items()
                },
            }

        energy_after = _energy_snapshot(tuple(self.energy_before))
        deltas: list[int] = []
        for path, (before, maximum) in self.energy_before.items():
            current = energy_after.get(path)
            if current is None:
                continue
            delta = current[0] - before
            if delta < 0 and maximum:
                delta += maximum
            if delta >= 0:
                deltas.append(delta)
        if deltas:
            energy: dict[str, Any] = {
                "available": True,
                "provider": "linux-rapl",
                "scope": "host",
                "energy_joules": round(sum(deltas) / 1_000_000, 6),
                "counter_count": len(deltas),
            }
        else:
            energy = {
                "available": False,
                "provider": None,
                "scope": None,
                "detail": "nessun contatore energetico leggibile senza privilegi",
            }
        return {
            "schema_version": 1,
            "process": process,
            "energy": energy,
            "system_load_average": {
                "before": self.load_before,
                "after": _load_average(),
            },
        }

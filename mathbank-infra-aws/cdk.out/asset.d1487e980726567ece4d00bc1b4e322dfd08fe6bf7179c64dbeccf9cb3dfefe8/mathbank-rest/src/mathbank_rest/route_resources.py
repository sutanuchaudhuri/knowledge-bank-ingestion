"""Conservative OS/model resource sizing, without installing discovery packages."""

import os
import platform
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass

GIB = 1024**3


def output(args: list[str]) -> str:
    return subprocess.check_output(args, text=True, timeout=15).strip()


@dataclass(frozen=True)
class Resources:
    os: str
    cpu_count: int
    total_memory: int
    available_memory: int
    gpu_available_memory: int | None = None


def discover() -> Resources:
    system = platform.system()
    cpus = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count()
    if system == "Darwin":
        total = int(output(["sysctl", "-n", "hw.memsize"]))
        vm = output(["vm_stat"])
        page = re.search(r"page size of (\d+) bytes", vm)
        if not page:
            raise ValueError("Cannot determine macOS memory page size.")
        counts = {}
        for line in vm.splitlines()[1:]:
            match = re.match(r"([^:]+):\s+(\d+)\.", line)
            if match:
                counts[match[1]] = int(match[2])
        # Do not count compressed/wired pages or double-count purgeable pages.
        available = sum(
            counts[key]
            for key in (
                "Pages free",
                "Pages inactive",
                "Pages speculative",
            )
        ) * int(page[1])
    elif system == "Linux":
        from pathlib import Path

        values = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            values[key] = int(value.strip().split()[0]) * 1024
        total, available = values["MemTotal"], values["MemAvailable"]
    else:
        raise ValueError("Automatic resource sizing currently supports macOS and Linux only.")
    gpu = None
    if system == "Linux" and shutil.which("nvidia-smi"):
        # Do not sum GPUs: a model/slot must fit an individual device.
        memory = output(
            [
                "nvidia-smi",
                "--query-gpu=memory.free",
                "--format=csv,noheader,nounits",
            ]
        )
        gpu = min(int(line) for line in memory.splitlines()) * 1024**2
    return Resources(system, cpus or 1, total, available, gpu)


def capacity(
    resources: Resources, model_bytes: int, context: int, requested: int | None = None
) -> dict:
    if model_bytes <= 0 or not 2048 <= context <= 32768:
        raise ValueError("Positive installed model size and supported context are required.")
    reserve = max(3 * GIB, int(resources.total_memory * 0.20))
    model = int(model_bytes * 1.25)  # Weights plus conservative runtime overhead.
    slot = max(GIB, int(1.5 * GIB * context / 16384))
    safe = min(resources.cpu_count, (resources.available_memory - reserve - model) // slot)
    if resources.gpu_available_memory is not None:
        safe = min(safe, (resources.gpu_available_memory - GIB - model) // slot)
    if safe < 1:
        raise ValueError(
            "Insufficient available memory for one safe inference slot; free memory or use a smaller model."
        )
    if requested is not None and not 1 <= requested <= safe:
        raise ValueError(f"Requested workers exceed the calculated safe ceiling ({safe}).")
    workers = requested or safe
    return {
        **asdict(resources),
        "model_bytes": model_bytes,
        "reserved_bytes": reserve,
        "estimated_model_bytes": model,
        "estimated_slot_bytes": slot,
        "safe_worker_ceiling": safe,
        "workers": workers,
        "num_thread": min(10, max(1, resources.cpu_count // workers)),
        "num_ctx": context,
        "total_memory_gib": round(resources.total_memory / GIB, 2),
        "available_memory_gib": round(resources.available_memory / GIB, 2),
        "estimated_model_gib": round(model / GIB, 2),
        "estimated_slot_gib": round(slot / GIB, 2),
        "sizing_policy": "conservative-estimate-v1",
    }

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import psutil

_GiB = 1024**3


@dataclass(frozen=True)
class SystemLoadState:
    id: str
    captured_at: datetime
    cpu_percent: float
    cpu_count_logical: int
    memory_used_bytes: int
    memory_total_bytes: int
    memory_percent: float
    swap_percent: float

    def prompt_section(self) -> str:
        used_gib = self.memory_used_bytes / _GiB
        total_gib = self.memory_total_bytes / _GiB if self.memory_total_bytes else 0.0
        return (
            f"CPU usage (sampled ~100ms): {self.cpu_percent:.1f}% "
            f"({self.cpu_count_logical} logical processors)\n"
            f"RAM: {self.memory_percent:.1f}% used ({used_gib:.2f} / {total_gib:.2f} GiB)\n"
            f"Swap / page file use: {self.swap_percent:.1f}%"
        )

class SystemLoadCollector:
    def __init__(self, cpu_sample_interval: float = 0.1) -> None:
        self._cpu_interval = max(0.0, float(cpu_sample_interval))

    def collect(self) -> SystemLoadState:
        n = psutil.cpu_count(logical=True) or 1
        if self._cpu_interval > 0:
            cpu = float(psutil.cpu_percent(interval=self._cpu_interval))
        else:
            cpu = float(psutil.cpu_percent(interval=None))
        vm = psutil.virtual_memory()
        sm = psutil.swap_memory()
        return SystemLoadState(
            id=str(uuid.uuid4()),
            captured_at=datetime.now(timezone.utc),
            cpu_percent=cpu,
            cpu_count_logical=int(n),
            memory_used_bytes=int(vm.used),
            memory_total_bytes=int(vm.total),
            memory_percent=float(vm.percent),
            swap_percent=float(sm.percent),
        )

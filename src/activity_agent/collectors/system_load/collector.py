from __future__ import annotations

import uuid
from datetime import datetime, timezone

import psutil

from activity_agent.core.models import SystemLoadState


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

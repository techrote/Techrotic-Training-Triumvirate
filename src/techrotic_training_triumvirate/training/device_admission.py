"""Pin GPU execution to a physical UUID rather than a remappable ordinal."""

from __future__ import annotations

import csv
import io
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, Self
from uuid import UUID

from techrotic_training_triumvirate.schemas import JsonObject


class DeviceAdmissionError(ValueError):
    """The worker cannot establish the identity of its admitted physical GPU."""


def _uuid(value: str) -> str:
    try:
        return f"GPU-{UUID(value.removeprefix('GPU-'))}"
    except ValueError as exc:
        raise DeviceAdmissionError(
            "GPU identity must be a full physical GPU UUID"
        ) from exc


@dataclass(frozen=True, slots=True)
class GPUSelection:
    driver_index: int | None
    uuid: str
    name: str | None
    pci_bus_id: str | None

    @classmethod
    def from_uuid(cls, uuid: str) -> Self:
        """Admit an explicit UUID even when unrelated lost devices break inventory.

        Physical name and UUID are read back from CUDA before model loading.
        Unknown inventory metadata remains null rather than being invented.
        """
        return cls(None, _uuid(uuid), None, None)

    def to_dict(self) -> JsonObject:
        return {
            "driver_index": self.driver_index,
            "uuid": self.uuid,
            "name": self.name,
            "pci_bus_id": self.pci_bus_id,
        }

    def environment(self, base: Mapping[str, str]) -> dict[str, str]:
        """Set physical selection before any CUDA/torch/model initialization."""
        return {
            **base,
            "CUDA_VISIBLE_DEVICES": _uuid(self.uuid),
            "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
        }


def select_gpu_from_inventory(text: str, *, driver_index: int) -> GPUSelection:
    """Resolve one nvidia-smi index to its immutable UUID from a single snapshot."""
    if type(driver_index) is not int or driver_index < 0:
        raise DeviceAdmissionError("driver GPU index must be a nonnegative integer")
    devices: list[GPUSelection] = []
    try:
        for row in csv.reader(io.StringIO(text)):
            if len(row) != 4:
                raise DeviceAdmissionError(
                    "GPU inventory must contain index,uuid,name,pci.bus_id"
                )
            index, uuid, name, pci_bus_id = (field.strip() for field in row)
            if not name or not pci_bus_id:
                raise DeviceAdmissionError(
                    "GPU inventory lacks physical device metadata"
                )
            devices.append(GPUSelection(int(index), _uuid(uuid), name, pci_bus_id))
    except (ValueError, csv.Error) as exc:
        if isinstance(exc, DeviceAdmissionError):
            raise
        raise DeviceAdmissionError(f"invalid GPU inventory: {exc}") from exc
    if len({device.driver_index for device in devices}) != len(devices) or len(
        {device.uuid for device in devices}
    ) != len(devices):
        raise DeviceAdmissionError("GPU inventory contains duplicate indices or UUIDs")
    selected = [device for device in devices if device.driver_index == driver_index]
    if len(selected) != 1:
        raise DeviceAdmissionError(
            "selected physical GPU is absent from driver inventory"
        )
    return selected[0]


def probe_gpu_selection(*, driver_index: int) -> GPUSelection:
    """Run a bounded driver query; this does not import or initialize CUDA."""
    try:
        probe = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,uuid,name,pci.bus_id",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DeviceAdmissionError(
            f"cannot establish physical GPU identity: {exc}"
        ) from exc
    return select_gpu_from_inventory(probe.stdout, driver_index=driver_index)


class CUDADeviceProperties(Protocol):
    uuid: str
    name: str


class CUDARuntime(Protocol):
    def device_count(self) -> int: ...

    def get_device_properties(self, device: int) -> CUDADeviceProperties: ...


def verify_selected_cuda(
    selection: GPUSelection, *, cuda: CUDARuntime, environment: Mapping[str, str]
) -> JsonObject:
    """Read back actual torch device zero after initialization and before models.

    The optional ML caller supplies ``torch.cuda``. Default tests supply a small
    deterministic double, so this module itself never imports torch.
    """
    expected = _uuid(selection.uuid)
    if environment.get("CUDA_VISIBLE_DEVICES") != expected:
        raise DeviceAdmissionError(
            "worker CUDA selection is not bound to the admitted UUID"
        )
    if cuda.device_count() != 1:
        raise DeviceAdmissionError("worker must expose exactly one admitted CUDA GPU")
    properties = cuda.get_device_properties(0)
    actual = _uuid(properties.uuid)
    if actual != expected:
        raise DeviceAdmissionError(
            "actual CUDA GPU UUID differs from the admitted physical device"
        )
    return {
        **selection.to_dict(),
        "actual_cuda_uuid": actual,
        "actual_cuda_name": properties.name,
        "visible_cuda_ordinal": 0,
        "identity_verified": True,
    }


def verify_cuda_environment(
    *, cuda: CUDARuntime, environment: Mapping[str, str]
) -> JsonObject:
    """Require an explicit single-GPU UUID environment before loading any model."""
    selection = GPUSelection.from_uuid(environment.get("CUDA_VISIBLE_DEVICES", ""))
    return verify_selected_cuda(selection, cuda=cuda, environment=environment)

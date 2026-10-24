"""Physical GPU UUID selection remains stable across CUDA ordinal remapping."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from techrotic_training_triumvirate.training.device_admission import (
    DeviceAdmissionError,
    GPUSelection,
    select_gpu_from_inventory,
    verify_cuda_environment,
    verify_selected_cuda,
)

V100 = "GPU-11111111-1111-1111-1111-111111111111"
TITAN = "GPU-22222222-2222-2222-2222-222222222222"
INVENTORY = (
    f"0, {V100}, Tesla V100, 00000000:01:00.0\n"
    f"1, {TITAN}, TITAN RTX, 00000000:02:00.0\n"
)


@dataclass
class Properties:
    uuid: str = TITAN
    name: str = "TITAN RTX"


class CudaDouble:
    def __init__(self, *, uuid: str = TITAN, count: int = 1) -> None:
        self.uuid, self.count = uuid, count

    def device_count(self) -> int:
        return self.count

    def get_device_properties(self, device: int) -> Properties:
        assert device == 0
        return Properties(self.uuid)


def test_titan_selection_uses_uuid_even_when_visible_ordinal_changes_to_zero() -> None:
    selected = select_gpu_from_inventory(INVENTORY, driver_index=1)
    environment = selected.environment(
        {"OTHER": "retained", "CUDA_VISIBLE_DEVICES": "0"}
    )
    assert selected.driver_index == 1
    assert environment["CUDA_VISIBLE_DEVICES"] == TITAN
    assert environment["OTHER"] == "retained"
    assert environment["CUDA_DEVICE_ORDER"] == "PCI_BUS_ID"
    actual = verify_selected_cuda(selected, cuda=CudaDouble(), environment=environment)
    assert actual["actual_cuda_uuid"] == TITAN
    assert actual["visible_cuda_ordinal"] == 0
    assert actual["identity_verified"] is True


def test_numeric_environment_selection_is_refused_before_cuda_inspection() -> None:
    selected = select_gpu_from_inventory(INVENTORY, driver_index=1)
    with pytest.raises(DeviceAdmissionError, match="bound to the admitted UUID"):
        verify_selected_cuda(
            selected, cuda=CudaDouble(), environment={"CUDA_VISIBLE_DEVICES": "0"}
        )


def test_actual_v100_is_refused_even_when_titan_was_requested() -> None:
    selected = select_gpu_from_inventory(INVENTORY, driver_index=1)
    with pytest.raises(DeviceAdmissionError, match="actual CUDA GPU UUID differs"):
        verify_selected_cuda(
            selected, cuda=CudaDouble(uuid=V100), environment=selected.environment({})
        )


def test_multiple_visible_cuda_devices_refuse() -> None:
    selected = select_gpu_from_inventory(INVENTORY, driver_index=1)
    with pytest.raises(DeviceAdmissionError, match="exactly one"):
        verify_selected_cuda(
            selected, cuda=CudaDouble(count=2), environment=selected.environment({})
        )


def test_raw_torch_uuid_without_gpu_prefix_can_match_physical_inventory() -> None:
    selected = select_gpu_from_inventory(INVENTORY, driver_index=1)
    actual = verify_selected_cuda(
        selected,
        cuda=CudaDouble(uuid=TITAN.removeprefix("GPU-")),
        environment=selected.environment({}),
    )
    assert actual["actual_cuda_uuid"] == TITAN


@pytest.mark.parametrize("physical", [TITAN, V100])
def test_native_torch_uuid_object_preserves_physical_identity(physical: str) -> None:
    class NativeUUID:
        def __str__(self) -> str:
            return physical.removeprefix("GPU-")

    class NativeCuda:
        def device_count(self) -> int:
            return 1

        def get_device_properties(self, device: int) -> SimpleNamespace:
            assert device == 0
            return SimpleNamespace(uuid=NativeUUID(), name="native torch property")

    environment = GPUSelection.from_uuid(TITAN).environment({})
    if physical != TITAN:
        with pytest.raises(DeviceAdmissionError, match="actual CUDA GPU UUID differs"):
            verify_cuda_environment(cuda=NativeCuda(), environment=environment)
    else:
        assert (
            verify_cuda_environment(cuda=NativeCuda(), environment=environment)[
                "actual_cuda_uuid"
            ]
            == TITAN
        )


@pytest.mark.parametrize(
    "text",
    [
        "",
        "invalid",
        INVENTORY + INVENTORY,
        "0, not-a-uuid, TITAN, pci",
        f"0, {TITAN}, , pci",
    ],
)
def test_missing_ambiguous_or_malformed_inventory_refuses(text: str) -> None:
    with pytest.raises(DeviceAdmissionError):
        select_gpu_from_inventory(text, driver_index=1)


def test_invalid_driver_index_and_uuid_refuse() -> None:
    with pytest.raises(DeviceAdmissionError):
        select_gpu_from_inventory(INVENTORY, driver_index=-1)
    with pytest.raises(DeviceAdmissionError):
        GPUSelection(0, "GPU-mutable", "TITAN", "pci").environment({})


def test_explicit_uuid_admission_requires_no_driver_inventory_query() -> None:
    selected = GPUSelection.from_uuid(TITAN)
    assert selected.driver_index is None
    assert selected.name is None
    actual = verify_cuda_environment(
        cuda=CudaDouble(), environment=selected.environment({})
    )
    assert actual["actual_cuda_uuid"] == TITAN
    assert actual["actual_cuda_name"] == "TITAN RTX"


@pytest.mark.parametrize("value", ["", "0", "1", "0,1", "GPU-unknown"])
def test_worker_environment_must_pin_one_full_uuid(value: str) -> None:
    with pytest.raises(DeviceAdmissionError):
        verify_cuda_environment(
            cuda=CudaDouble(), environment={"CUDA_VISIBLE_DEVICES": value}
        )

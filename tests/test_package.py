from __future__ import annotations

import techrotic_training_triumvirate as ttt


def test_package_import_and_version() -> None:
    assert ttt.__version__ == "0.1.0"

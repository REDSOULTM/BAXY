from __future__ import annotations

from pathlib import Path

import pytest

from scripts.verify_python_runtime_lock import (
    EXPECTED_ENVIRONMENT,
    RuntimeLockError,
    load_constraints,
    validate_current_interpreter,
    validate_installed_distributions,
    validate_lock_structure,
)


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "pylock.runtime-win-x64.toml"
CONSTRAINTS = ROOT / "constraints-runtime-win-x64.txt"
TEST_LOCK = ROOT / "pylock.test-win-x64.toml"
TEST_CONSTRAINTS = ROOT / "constraints-test-win-x64.txt"


def test_runtime_lock_matches_the_measured_product_graph() -> None:
    locked = validate_lock_structure(LOCK, CONSTRAINTS)

    assert len(locked) == 60
    assert locked["pywebrtc-audio"] == "0.2.0+baxy.1"
    assert not {"ai-edge-litert", "backports-strenum", "ml-dtypes"} & locked.keys()
    assert locked == load_constraints(CONSTRAINTS)
    assert locked["numpy"] == "1.26.4"
    assert locked["torch"] == "2.13.0"
    assert locked["sherpa-onnx"] == "1.13.4+baxy.2"
    assert locked["sherpa-onnx-core"] == "1.13.4"
    assert "pytest" not in locked
    assert "pip" not in locked


def test_registered_test_runtime_contains_the_locked_product_graph() -> None:
    runtime = validate_lock_structure(LOCK, CONSTRAINTS)
    test = validate_lock_structure(TEST_LOCK, TEST_CONSTRAINTS)

    validate_current_interpreter()
    validate_installed_distributions(runtime)
    validate_installed_distributions(test)


def test_test_lock_is_separate_and_contains_only_the_pytest_graph() -> None:
    locked = validate_lock_structure(TEST_LOCK, TEST_CONSTRAINTS)

    assert len(locked) == 6
    assert locked["pytest"] == "9.1.1"
    assert locked["pluggy"] == "1.6.0"
    assert "torch" not in locked


def test_runtime_lock_rejects_an_environment_broader_than_the_wheels(
    tmp_path: Path,
) -> None:
    broadened = LOCK.read_text(encoding="utf-8").replace(
        f'environments = ["{EXPECTED_ENVIRONMENT}"]',
        'environments = ["sys_platform == \'win32\'"]',
        1,
    )
    candidate = tmp_path / "pylock.runtime-win-x64.toml"
    candidate.write_text(broadened, encoding="utf-8")

    with pytest.raises(RuntimeLockError, match="^lock_environment$"):
        validate_lock_structure(candidate, CONSTRAINTS)


def test_runtime_lock_rejects_a_wheel_hash_without_full_sha256(
    tmp_path: Path,
) -> None:
    malformed = LOCK.read_text(encoding="utf-8").replace(
        'sha256 = "',
        'sha256 = "00',
        1,
    )
    candidate = tmp_path / "pylock.runtime-win-x64.toml"
    candidate.write_text(malformed, encoding="utf-8")

    with pytest.raises(RuntimeLockError, match="^lock_wheel_identity$"):
        validate_lock_structure(candidate, CONSTRAINTS)


def test_runtime_lock_rejects_a_wheel_for_an_unannounced_platform(
    tmp_path: Path,
) -> None:
    incompatible = LOCK.read_text(encoding="utf-8").replace(
        "cffi-2.1.0-cp312-cp312-win_amd64.whl",
        "cffi-2.1.0-cp312-cp312-manylinux_2_28_x86_64.whl",
    )
    candidate = tmp_path / "pylock.runtime-win-x64.toml"
    candidate.write_text(incompatible, encoding="utf-8")

    with pytest.raises(RuntimeLockError, match="^lock_wheel_tags$"):
        validate_lock_structure(candidate, CONSTRAINTS)


def test_runtime_lock_rejects_unhashed_url_state(tmp_path: Path) -> None:
    redirected = LOCK.read_text(encoding="utf-8").replace(
        '.whl"\n\n[packages.wheels.hashes]',
        '.whl?download=1"\n\n[packages.wheels.hashes]',
        1,
    )
    candidate = tmp_path / "pylock.runtime-win-x64.toml"
    candidate.write_text(redirected, encoding="utf-8")

    with pytest.raises(RuntimeLockError, match="^lock_wheel_source$"):
        validate_lock_structure(candidate, CONSTRAINTS)


def test_runtime_lock_rejects_unreviewed_top_level_behavior(
    tmp_path: Path,
) -> None:
    extended = LOCK.read_text(encoding="utf-8").replace(
        'created-by = "pip"\n',
        'created-by = "pip"\nmarker = "unreviewed"\n',
        1,
    )
    candidate = tmp_path / "pylock.runtime-win-x64.toml"
    candidate.write_text(extended, encoding="utf-8")

    with pytest.raises(RuntimeLockError, match="^lock_fields$"):
        validate_lock_structure(candidate, CONSTRAINTS)


@pytest.mark.parametrize("prefix", ["../runtime_wheels/", "D:/runtime_wheels/", "other/"])
def test_runtime_lock_rejects_local_wheels_outside_the_bundle(
    tmp_path: Path, prefix: str,
) -> None:
    content = LOCK.read_text(encoding="utf-8")
    assert 'path = "runtime_wheels/' in content
    candidate = tmp_path / "pylock.runtime-win-x64.toml"
    candidate.write_text(content.replace('path = "runtime_wheels/', f'path = "{prefix}'), encoding="utf-8")

    with pytest.raises(RuntimeLockError, match="^lock_wheel_source$"):
        validate_lock_structure(candidate, CONSTRAINTS)


def test_runtime_lock_rejects_a_path_disguised_as_a_wheel_name(tmp_path: Path) -> None:
    original = LOCK.read_text(encoding="utf-8")
    content = original.replace(
        'name = "sherpa_onnx-',
        'name = "../sherpa_onnx-',
    )
    assert content != original
    candidate = tmp_path / "pylock.runtime-win-x64.toml"
    candidate.write_text(content, encoding="utf-8")

    with pytest.raises(RuntimeLockError, match="^lock_wheel_identity$"):
        validate_lock_structure(candidate, CONSTRAINTS)

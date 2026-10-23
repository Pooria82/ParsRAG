"""Settings that apply without a restart: validation, persistence, and API."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    get_read_runtime_settings,
    get_update_runtime_settings,
)
from backend.core.domain.exceptions import InvalidInputError
from backend.core.domain.runtime_settings import (
    RUNTIME_SETTINGS,
    SETTINGS_BY_KEY,
    normalize_setting,
)
from backend.core.dto.input.runtime_settings import RuntimeSettingsUpdate
from backend.core.use_case.system.runtime_settings import (
    ReadRuntimeSettings,
    UpdateRuntimeSettings,
)
from backend.infrastructure.runtime_settings import (
    EnvironmentSettingsStore,
    runtime_settings_path,
)
from backend.main import app

MB = 1024 * 1024
CEILING = 500 * MB


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test from .env values chosen by the test."""
    for spec in RUNTIME_SETTINGS:
        monkeypatch.delenv(spec.key, raising=False)


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("OCR_ENABLED", True, "1"),
        ("OCR_ENABLED", "off", "0"),
        ("STRICT_RAG_THRESHOLD", 0.8, "0.8"),
        ("STRICT_RAG_THRESHOLD", "0.65", "0.65"),
        ("OCR_DPI", 300, "300"),
        ("OCR_DPI", "300.0", "300"),
        ("STRICT_RAG_TOP_K", None, ""),
        ("STRICT_RAG_TOP_K", "", ""),
        ("OCR_LANGUAGES", " FAS+eng ", "fas+eng"),
        ("PARSRAG_MAX_FILE_BYTES", 20 * MB, str(20 * MB)),
    ],
)
def test_values_are_normalized_to_environment_strings(
    key: str, value: object, expected: str
) -> None:
    assert normalize_setting(SETTINGS_BY_KEY[key], value) == expected  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("OCR_DPI", 100),
        ("OCR_DPI", 12.5),
        ("OCR_DPI", True),
        ("OCR_DPI", "many"),
        ("STRICT_RAG_THRESHOLD", 1.5),
        ("STRICT_RAG_THRESHOLD", "nan"),
        ("OCR_ENABLED", "maybe"),
        ("OCR_LANGUAGES", "fas;rm -rf"),
        ("OCR_DPI", None),
    ],
)
def test_invalid_values_are_rejected(key: str, value: object) -> None:
    with pytest.raises(ValueError):
        normalize_setting(SETTINGS_BY_KEY[key], value)  # type: ignore[arg-type]


def test_every_setting_default_is_valid() -> None:
    for spec in RUNTIME_SETTINGS:
        assert normalize_setting(spec, spec.default) == spec.default


def test_overrides_change_the_environment_and_survive_a_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    monkeypatch.setenv("OCR_MAX_IMAGES", "30")
    path = tmp_path / "runtime-settings.json"
    changed: list[set[str]] = []
    store = EnvironmentSettingsStore(path, on_change=changed.append)

    store.apply({"OCR_MAX_IMAGES": "200", "OCR_DPI": "300"})

    assert os.environ["OCR_MAX_IMAGES"] == "200"
    assert store.values()["OCR_MAX_IMAGES"] == "200"
    assert store.env_values()["OCR_MAX_IMAGES"] == "30"
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "OCR_DPI": "300",
        "OCR_MAX_IMAGES": "200",
    }
    assert changed == [{"OCR_MAX_IMAGES", "OCR_DPI"}]

    monkeypatch.setenv("OCR_MAX_IMAGES", "30")
    monkeypatch.delenv("OCR_DPI")
    restarted = EnvironmentSettingsStore(path)
    assert os.environ["OCR_MAX_IMAGES"] == "200"
    assert restarted.overrides() == {"OCR_DPI": "300", "OCR_MAX_IMAGES": "200"}

    restarted.apply({"OCR_MAX_IMAGES": None, "OCR_DPI": None})
    assert os.environ["OCR_MAX_IMAGES"] == "30"
    assert "OCR_DPI" not in os.environ
    assert not path.exists()


def test_unreadable_or_invalid_saved_settings_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "runtime-settings.json"
    path.write_text("{not json", encoding="utf-8")
    assert EnvironmentSettingsStore(path).overrides() == {}

    path.write_text(
        json.dumps({"OCR_DPI": "9999", "UNKNOWN": "1", "OCR_MAX_PAGES": "40"}),
        encoding="utf-8",
    )
    assert EnvironmentSettingsStore(path).overrides() == {"OCR_MAX_PAGES": "40"}


def test_invalid_env_values_show_the_built_in_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OCR_DPI", "lots")
    store = EnvironmentSettingsStore(tmp_path / "s.json")
    assert store.env_values()["OCR_DPI"] == "200"


def test_settings_file_sits_next_to_the_model_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PARSRAG_SETTINGS_PATH", raising=False)
    monkeypatch.setenv(
        "PARSRAG_CONFIG_PATH", "/var/lib/parsrag/model-configuration.json"
    )
    assert runtime_settings_path() == Path("/var/lib/parsrag/runtime-settings.json")
    monkeypatch.setenv("PARSRAG_SETTINGS_PATH", "/tmp/custom.json")
    assert runtime_settings_path() == Path("/tmp/custom.json")


def _use_cases(tmp_path: Path) -> tuple[ReadRuntimeSettings, UpdateRuntimeSettings]:
    store = EnvironmentSettingsStore(tmp_path / "runtime-settings.json")
    return ReadRuntimeSettings(store, CEILING), UpdateRuntimeSettings(store, CEILING)


def test_reading_lists_every_setting_with_its_env_value(tmp_path: Path) -> None:
    read, update = _use_cases(tmp_path)
    update.execute(RuntimeSettingsUpdate(values={"OCR_DPI": 300}))

    response = read.execute()
    items = {item.key: item for item in response.settings}
    assert list(items) == [spec.key for spec in RUNTIME_SETTINGS]
    assert items["OCR_DPI"].value == "300"
    assert items["OCR_DPI"].env_value == "200"
    assert items["OCR_DPI"].overridden
    assert not items["OCR_MAX_PAGES"].overridden
    assert response.upload_ceiling_bytes == CEILING


@pytest.mark.parametrize(
    ("values", "code"),
    [
        ({"PARSRAG_ALLOWED_HOSTS": "evil.example"}, "invalid_setting"),
        ({"OCR_DPI": 5}, "invalid_setting"),
        (
            {"PARSRAG_MAX_FILE_BYTES": 300 * MB, "PARSRAG_MAX_BATCH_BYTES": 200 * MB},
            "invalid_setting",
        ),
        ({"PARSRAG_MAX_BATCH_BYTES": 600 * MB}, "upload_ceiling"),
    ],
)
def test_unsafe_or_contradictory_changes_are_refused(
    tmp_path: Path, values: dict[str, object], code: str
) -> None:
    _, update = _use_cases(tmp_path)
    with pytest.raises(InvalidInputError) as raised:
        update.execute(RuntimeSettingsUpdate.model_validate({"values": values}))
    assert raised.value.code == code


def test_reset_returns_every_setting_to_env(tmp_path: Path) -> None:
    read, update = _use_cases(tmp_path)
    update.execute(
        RuntimeSettingsUpdate(values={"OCR_DPI": 300, "KEYWORD_SEARCH": False})
    )

    update.reset()

    assert not any(item.overridden for item in read.execute().settings)


def test_settings_api_reads_changes_and_resets(tmp_path: Path) -> None:
    store = EnvironmentSettingsStore(tmp_path / "runtime-settings.json")
    app.dependency_overrides[get_read_runtime_settings] = lambda: ReadRuntimeSettings(
        store, CEILING
    )
    app.dependency_overrides[get_update_runtime_settings] = lambda: (
        UpdateRuntimeSettings(store, CEILING)
    )
    client = TestClient(app)
    try:
        listed = client.get("/settings/runtime")
        changed = client.put(
            "/settings/runtime", json={"values": {"OCR_MAX_IMAGES": 150}}
        )
        refused = client.put("/settings/runtime", json={"values": {"OCR_DPI": 1}})
        reset = client.delete("/settings/runtime")
    finally:
        app.dependency_overrides.clear()

    assert listed.status_code == 200
    assert {item["group"] for item in listed.json()["settings"]} == {
        "model",
        "retrieval",
        "documents",
        "performance",
        "updates",
    }
    assert changed.status_code == 200
    images = next(
        item for item in changed.json()["settings"] if item["key"] == "OCR_MAX_IMAGES"
    )
    assert images["value"] == "150" and images["overridden"]
    assert refused.status_code == 400
    assert refused.json()["code"] == "invalid_setting"
    assert not any(item["overridden"] for item in reset.json()["settings"])


@patch("backend.infrastructure.llm.factory.configure_model")
def test_model_settings_rebuild_the_model_clients(mock_configure: MagicMock) -> None:
    from backend.infrastructure.llm import factory

    factory.apply_runtime_settings({"OCR_DPI"})
    mock_configure.assert_not_called()

    factory.apply_runtime_settings({"OLLAMA_CONTEXT_LENGTH"})
    mock_configure.assert_called_once()
    assert mock_configure.call_args.kwargs == {"verify": False, "persist": False}


def test_embedding_batch_size_follows_the_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.infrastructure.llm import factory

    monkeypatch.setattr(factory, "_embedding_device", "cpu")
    with patch("backend.infrastructure.llm.factory.Settings") as settings:
        monkeypatch.setenv("EMBED_BATCH_SIZE", "24")
        factory.apply_runtime_settings({"EMBED_BATCH_SIZE"})
        assert settings.embed_model.embed_batch_size == 24
        monkeypatch.delenv("EMBED_BATCH_SIZE")
        factory.apply_runtime_settings({"EMBED_BATCH_SIZE"})
        assert settings.embed_model.embed_batch_size == 8


def test_cpu_threads_are_applied_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.infrastructure.llm import factory

    monkeypatch.delenv("PARSRAG_CPU_THREADS", raising=False)
    with patch("backend.infrastructure.llm.factory.torch.set_num_threads") as threads:
        monkeypatch.setenv("PARSRAG_CPU_THREADS", "6")
        factory.apply_runtime_settings({"PARSRAG_CPU_THREADS"})
        threads.assert_called_once_with(6)
        # Resetting to automatic restores the startup count, not the override.
        monkeypatch.delenv("PARSRAG_CPU_THREADS")
        factory.apply_runtime_settings({"PARSRAG_CPU_THREADS"})
        threads.assert_called_with(factory._DEFAULT_CPU_THREADS)


def test_automatic_settings_report_the_value_in_use(tmp_path: Path) -> None:
    store = EnvironmentSettingsStore(
        tmp_path / "s.json", automatic=lambda: {"OCR_WORKERS": "4", "OCR_DPI": "x"}
    )
    items = {
        item.key: item
        for item in ReadRuntimeSettings(store, CEILING).execute().settings
    }

    assert items["OCR_WORKERS"].automatic_value == "4"
    # Only settings that can be automatic carry a value.
    assert items["OCR_DPI"].automatic_value is None
    assert items["STRICT_RAG_TOP_K"].automatic_value is None


def test_server_reports_what_automatic_means(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.infrastructure.llm import factory

    monkeypatch.setattr(factory, "_embedding_device", "cpu")
    monkeypatch.setattr(factory, "_DEFAULT_CPU_THREADS", 6)
    with patch(
        "backend.infrastructure.llm.factory.default_ocr_workers", return_value=5
    ):
        values = factory.automatic_setting_values()

    assert values == {
        "STRICT_RAG_TOP_K": "8-30",
        "HYBRID_RERANK_TOP_K": "8-30",
        "OCR_WORKERS": "5",
        "EMBED_BATCH_SIZE": "8",
        "PARSRAG_CPU_THREADS": "6",
    }
    automatic = {spec.key for spec in RUNTIME_SETTINGS if spec.automatic}
    assert set(values) == automatic


def test_a_failed_save_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read-only volume or full disk must not leave live but unsaved values."""
    monkeypatch.setenv("OCR_MAX_PAGES", "30")
    changed: list[set[str]] = []
    store = EnvironmentSettingsStore(tmp_path / "s.json", on_change=changed.append)

    with (
        patch.object(store, "_save", side_effect=OSError("read-only")),
        pytest.raises(OSError),
    ):
        store.apply({"OCR_MAX_PAGES": "40"})

    assert store.overrides() == {}
    assert store.values()["OCR_MAX_PAGES"] == "30"
    import os

    assert os.environ["OCR_MAX_PAGES"] == "30"
    assert changed == []


def test_upload_limits_are_checked_inside_the_store_lock(tmp_path: Path) -> None:
    """The check sees the values the change would produce, under the lock."""
    store = EnvironmentSettingsStore(tmp_path / "s.json")
    seen: list[dict[str, str]] = []

    def validate(values: dict[str, str]) -> None:
        assert store._lock._is_owned()  # type: ignore[attr-defined]
        seen.append(values)
        raise InvalidInputError("no", code="invalid_setting")

    with pytest.raises(InvalidInputError):
        store.apply({"PARSRAG_MAX_FILE_BYTES": str(600 * MB)}, validate=validate)

    assert seen[0]["PARSRAG_MAX_FILE_BYTES"] == str(600 * MB)
    assert store.overrides() == {}

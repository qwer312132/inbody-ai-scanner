from pathlib import Path
from unittest.mock import patch

from ai import inbody_analyzer


def test_model_is_not_loaded_on_module_import():
    """API-only tests must not need a local YOLO weight file."""
    inbody_analyzer.get_model.cache_clear()

    with patch.object(inbody_analyzer, "MODEL_PATH", Path("missing-model.pt")):
        assert not inbody_analyzer.MODEL_PATH.exists()


def test_get_model_reports_a_clear_error_when_weights_are_missing():
    inbody_analyzer.get_model.cache_clear()

    with patch.object(inbody_analyzer, "MODEL_PATH", Path("missing-model.pt")):
        try:
            inbody_analyzer.get_model()
        except FileNotFoundError as exc:
            assert "YOLO model weights were not found" in str(exc)
        else:
            raise AssertionError("Expected missing model weights to raise FileNotFoundError")

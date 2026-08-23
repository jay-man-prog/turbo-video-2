from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from app.config import config


ROOT_DIR = Path(__file__).parent.parent.parent
WEBUI_MAIN = ROOT_DIR / "webui" / "Main.py"


def _widget_by_key(elements, key):
    return next(item for item in elements if str(getattr(item, "key", "")) == key)


def test_rh_simple_mode_is_the_default_and_exposes_the_short_workflow():
    with patch.object(config, "try_save_config", return_value=True):
        app = AppTest.from_file(str(WEBUI_MAIN), default_timeout=60)
        app.session_state["ui_language"] = "en"
        app.run()

    assert not [str(item.value) for item in app.exception]
    assert _widget_by_key(app.radio, "workflow_mode").value == "R&H Essendon Simple Mode"
    assert _widget_by_key(app.text_area, "rh_simple_topic")
    assert _widget_by_key(app.selectbox, "rh_simple_content_type").value == "Seller Tip"
    assert _widget_by_key(app.selectbox, "rh_simple_target_seconds").value == 20
    contact_card = _widget_by_key(app.selectbox, "rh_simple_final_contact_card")
    assert contact_card.value == "jayden_manno"
    assert list(contact_card.options) == [
        "Jayden Manno — Director and Auctioneer",
        "Raine & Horne Essendon — Office",
    ]
    assert _widget_by_key(app.checkbox, "rh_simple_music_enabled").value is True
    assert _widget_by_key(app.button, "rh_prepare_plan")

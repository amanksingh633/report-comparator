from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parent.parent / "app.py")


def test_app_prompts_for_uploads_by_default():
    at = AppTest.from_file(APP).run(timeout=30)
    assert not at.exception
    assert any("Upload both files" in i.value for i in at.info)


def test_app_runs_on_sample_data():
    at = AppTest.from_file(APP)
    at.run(timeout=30)
    at.sidebar.checkbox[0].check().run(timeout=30)
    assert not at.exception
    assert at.error[0].value == "FAIL: reports differ"
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Missing in candidate"] == "2"
    assert metrics["Extra in candidate"] == "2"
    assert metrics["Mismatched cells"] == "3"

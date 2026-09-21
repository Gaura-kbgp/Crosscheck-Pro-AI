from app.core.config import settings

def test_settings_load():
    assert settings.APP_NAME == "CrossCheckPro API"

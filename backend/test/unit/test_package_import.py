import sys


def test_import_zixuetong_does_not_eagerly_import_knowledge(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    sys.modules.pop("zixuetong", None)
    sys.modules.pop("zixuetong.knowledge", None)

    import zixuetong

    assert zixuetong.get_version() == zixuetong.__version__
    assert "zixuetong.knowledge" not in sys.modules

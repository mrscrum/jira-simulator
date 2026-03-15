import pytest


class TestSettings:
    def test_loads_default_database_url(self, monkeypatch):
        monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_EMAIL", "test@test.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "token123")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        from app.config import Settings

        settings = Settings()
        assert settings.database_url == "sqlite:///./data/simulator.db"

    def test_loads_default_environment(self, monkeypatch):
        monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_EMAIL", "test@test.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "token123")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        from app.config import Settings

        settings = Settings()
        assert settings.environment == "production"

    def test_loads_default_log_level(self, monkeypatch):
        monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_EMAIL", "test@test.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "token123")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        from app.config import Settings

        settings = Settings()
        assert settings.log_level == "INFO"

    def test_loads_default_tick_interval(self, monkeypatch):
        monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_EMAIL", "test@test.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "token123")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        from app.config import Settings

        settings = Settings()
        assert settings.tick_interval_minutes == 30

    def test_requires_jira_base_url(self, monkeypatch):
        monkeypatch.delenv("JIRA_BASE_URL", raising=False)
        monkeypatch.setenv("JIRA_EMAIL", "test@test.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "token123")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        from app.config import Settings

        with pytest.raises(Exception):
            Settings()

    def test_requires_openai_api_key(self, monkeypatch):
        monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_EMAIL", "test@test.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "token123")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        from app.config import Settings

        with pytest.raises(Exception):
            Settings()

    def test_overrides_from_environment(self, monkeypatch):
        monkeypatch.setenv("JIRA_BASE_URL", "https://custom.atlassian.net")
        monkeypatch.setenv("JIRA_EMAIL", "custom@test.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "custom-token")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-custom")
        monkeypatch.setenv("DATABASE_URL", "sqlite:///custom.db")
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("TICK_INTERVAL_MINUTES", "15")

        from app.config import Settings

        settings = Settings()
        assert settings.jira_base_url == "https://custom.atlassian.net"
        assert settings.jira_email == "custom@test.com"
        assert settings.jira_api_token == "custom-token"
        assert settings.openai_api_key == "sk-custom"
        assert settings.database_url == "sqlite:///custom.db"
        assert settings.environment == "development"
        assert settings.log_level == "DEBUG"
        assert settings.tick_interval_minutes == 15

    def test_get_settings_returns_instance(self, monkeypatch):
        monkeypatch.setenv("JIRA_BASE_URL", "https://test.atlassian.net")
        monkeypatch.setenv("JIRA_EMAIL", "test@test.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "token123")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        from app.config import get_settings

        settings = get_settings()
        assert settings.jira_base_url == "https://test.atlassian.net"

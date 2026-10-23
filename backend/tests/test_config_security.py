"""配置与生产环境自检测试。

生产环境的安全性不能依赖部署者"记得改"，必须有启动期硬校验。
本文件同时固定住校验逻辑本身，防止后续改动把闸门放空。
"""
from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.security import create_access_token, decode_access_token


def _prod(**overrides) -> Settings:
    base = {
        "environment": "production",
        "secret_key": "a" * 64,
        "postgres_password": "strong-random-password",
        "cors_origins": "https://lawpilot.example.com",
    }
    base.update(overrides)
    return Settings(**base)


class TestProductionGuard:
    def test_secure_config_passes(self) -> None:
        assert _prod().validate_for_production() == []

    def test_default_secret_key_rejected(self) -> None:
        problems = _prod(secret_key="dev_secret_change_me").validate_for_production()
        assert any("SECRET_KEY" in p for p in problems)
        assert any("开发默认值" in p for p in problems)

    def test_short_secret_key_rejected(self) -> None:
        problems = _prod(secret_key="tooshort").validate_for_production()
        assert any("长度不足" in p for p in problems)

    def test_default_db_password_rejected(self) -> None:
        problems = _prod(postgres_password="lawpilot_secret").validate_for_production()
        assert any("POSTGRES_PASSWORD" in p for p in problems)

    def test_wildcard_cors_rejected(self) -> None:
        problems = _prod(cors_origins="*").validate_for_production()
        assert any("通配符" in p for p in problems)

    def test_multiple_problems_all_reported(self) -> None:
        """自检应一次性列出全部问题，避免部署者反复试错。"""
        problems = _prod(
            secret_key="dev_secret_change_me",
            postgres_password="lawpilot_secret",
            cors_origins="*",
        ).validate_for_production()
        assert len(problems) >= 3

    @pytest.mark.parametrize("env", ["development", "test"])
    def test_non_production_is_not_blocked(self, env: str) -> None:
        s = Settings(environment=env, secret_key="dev_secret_change_me")
        assert s.validate_for_production() == []


class TestDocsExposure:
    def test_docs_default_on_for_development(self) -> None:
        assert Settings(environment="development").docs_enabled is True

    def test_docs_default_off_for_production(self) -> None:
        assert _prod().docs_enabled is False

    def test_docs_can_be_forced_on(self) -> None:
        assert _prod(expose_docs=True).docs_enabled is True

    def test_docs_can_be_forced_off_in_dev(self) -> None:
        assert Settings(environment="development", expose_docs=False).docs_enabled is False


class TestCorsParsing:
    def test_trims_and_drops_empties(self) -> None:
        s = Settings(cors_origins=" http://a.com , ,http://b.com ,")
        assert s.cors_origin_list == ["http://a.com", "http://b.com"]

    def test_single_origin(self) -> None:
        assert Settings(cors_origins="https://x.cn").cors_origin_list == ["https://x.cn"]


class TestKeyDerivation:
    def test_fernet_key_is_32_bytes(self) -> None:
        raw = Settings(secret_key="abc").ai_fernet_key
        assert len(raw) == 44  # urlsafe_b64encode(32) 恒为 44 字符

    def test_fernet_key_is_deterministic(self) -> None:
        a = Settings(secret_key="abc").ai_fernet_key
        b = Settings(secret_key="abc").ai_fernet_key
        assert a == b

    def test_fernet_key_changes_with_secret(self) -> None:
        assert Settings(secret_key="abc").ai_fernet_key != Settings(secret_key="abd").ai_fernet_key

    def test_explicit_encryption_key_takes_priority(self) -> None:
        s = Settings(secret_key="abc", ai_encryption_key="xyz")
        assert s.ai_fernet_key != Settings(secret_key="abc").ai_fernet_key


class TestJwtUsesConfiguredSecret:
    """回归保护：令牌必须绑定当前配置的密钥，不能被环境串味。"""

    def test_token_roundtrip_under_test_secret(self) -> None:
        token = create_access_token("u-1")
        assert decode_access_token(token)["sub"] == "u-1"

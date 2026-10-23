"""核心安全模块测试：密码哈希与 JWT。

覆盖三类风险：
1. 正确性：签发的令牌能被正确解码，密码哈希能正确校验；
2. 完整性：篡改载荷或签名后必须解码失败；
3. 时效与声明：过期令牌、错误 iss / aud 必须被拒绝。
"""
from __future__ import annotations

import pytest
from jose import JWTError
from jose import jwt as jose_jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self) -> None:
        hashed = hash_password("P@ssw0rd-123")
        assert hashed != "P@ssw0rd-123"
        assert hashed.startswith("$2")  # bcrypt 标识

    def test_hash_is_salted(self) -> None:
        """同一密码两次哈希结果必须不同（每次独立加盐）。"""
        assert hash_password("same") != hash_password("same")

    def test_verify_success(self) -> None:
        assert verify_password("P@ssw0rd-123", hash_password("P@ssw0rd-123")) is True

    @pytest.mark.parametrize("wrong", ["", "p@ssw0rd-123", "P@ssw0rd-123 ", "P@ssw0rd-12"])
    def test_verify_failure(self, wrong: str) -> None:
        assert verify_password(wrong, hash_password("P@ssw0rd-123")) is False


class TestAccessToken:
    def test_roundtrip(self) -> None:
        token = create_access_token(subject="user-42")
        claims = decode_access_token(token)
        assert claims["sub"] == "user-42"
        assert claims["iss"] == settings.jwt_issuer
        assert claims["aud"] == settings.jwt_audience
        assert "exp" in claims and "iat" in claims

    def test_extra_claims_preserved(self) -> None:
        token = create_access_token("u1", extra_claims={"role": "admin"})
        assert decode_access_token(token)["role"] == "admin"

    def test_tampered_payload_rejected(self) -> None:
        token = create_access_token("user-42")
        header, _payload, signature = token.split(".")
        forged = f"{header}.{_payload[:-2]}AA.{signature}"
        with pytest.raises(JWTError):
            decode_access_token(forged)

    def test_wrong_signature_rejected(self) -> None:
        token = create_access_token("user-42")
        header, payload, _sig = token.split(".")
        with pytest.raises(JWTError):
            decode_access_token(f"{header}.{payload}.forged-signature")

    def test_expired_token_rejected(self) -> None:
        token = create_access_token("user-42", expires_minutes=-1)
        with pytest.raises(JWTError):
            decode_access_token(token)

    def test_wrong_audience_rejected(self) -> None:
        """伪造受众（跨系统重放）必须失败。"""
        payload = {
            "sub": "user-42",
            "iss": settings.jwt_issuer,
            "aud": "another-service",
            "exp": 9_999_999_999,
        }
        token = jose_jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
        with pytest.raises(JWTError):
            decode_access_token(token)

    def test_wrong_issuer_rejected(self) -> None:
        payload = {
            "sub": "user-42",
            "iss": "evil-issuer",
            "aud": settings.jwt_audience,
            "exp": 9_999_999_999,
        }
        token = jose_jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
        with pytest.raises(JWTError):
            decode_access_token(token)

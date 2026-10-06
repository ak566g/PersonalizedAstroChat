import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from app.brain.resilient_repository import ScopedGraph
from app.profile.service import ProfileService
from app.storage.auth_store import Account, AuthStore

SALT_BYTES = 16


class InvalidCredentials(Exception):
    pass


@dataclass
class SignupResult:
    user_id: str
    session_token: str


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _hash_password(password: str, salt_hex: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt_hex), iterations
    ).hex()


class AuthService:
    def __init__(self, store: AuthStore, password_iterations: int) -> None:
        self._store = store
        self._iterations = password_iterations
        # Hashed against for unknown emails so login timing doesn't reveal which emails exist.
        self._dummy_salt = secrets.token_hex(SALT_BYTES)

    def signup(
        self, email: str, password: str, profile_fields: dict, graph: ScopedGraph
    ) -> SignupResult:
        user_id = str(uuid.uuid4())
        salt = secrets.token_hex(SALT_BYTES)
        self._store.create_account(
            Account(
                user_id,
                _normalize(email),
                _hash_password(password, salt, self._iterations),
                salt,
                self._iterations,
            )
        )
        try:
            ProfileService(graph).create(user_id, profile_fields)
        except Exception:
            # Don't leave an account with no profile that blocks re-signup with a 409.
            self._store.delete_account(user_id)
            raise
        return SignupResult(user_id, self._new_session(user_id))

    def login(self, email: str, password: str) -> str:
        account = self._store.get_account_by_email(_normalize(email))
        if account is None:
            _hash_password(password, self._dummy_salt, self._iterations)
            raise InvalidCredentials()
        candidate = _hash_password(
            password, account.password_salt, account.password_iterations
        )
        if not hmac.compare_digest(candidate, account.password_hash):
            raise InvalidCredentials()
        return self._new_session(account.user_id)

    def logout(self, token_hash: str) -> None:
        self._store.delete_session(token_hash)

    def user_for_token(self, token: str) -> str | None:
        return self._store.user_for_session(hash_token(token))

    def _new_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        self._store.create_session(hash_token(token), user_id)
        return token


def _normalize(email: str) -> str:
    return email.strip().lower()
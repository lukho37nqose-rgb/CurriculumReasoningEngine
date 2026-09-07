"""Demo-only identity sessions. No academic evidence is stored here."""

import secrets
import time
from dataclasses import dataclass

from .package import INSTITUTION

SUBJECTS = tuple(f"NS-{i:03}" for i in range(1, 16))


@dataclass(frozen=True)
class Session:
    subject_reference: str
    institution_id: str
    launch_request_id: str
    expires_at: float


class DemoIdentity:
    def __init__(self, lifetime=1800, clock=time.monotonic):
        self.lifetime = lifetime
        self.clock = clock
        self.sessions = {}

    def login(self, subject, access_code):
        if subject not in SUBJECTS or not secrets.compare_digest(str(access_code), "northstar-demo"):
            raise ValueError("Unknown demo account or access code")
        self._expire()
        token = secrets.token_urlsafe(32)
        self.sessions[token] = Session(subject, INSTITUTION, secrets.token_urlsafe(16), self.clock() + self.lifetime)
        return token

    def _expire(self):
        now = self.clock()
        self.sessions = {key: session for key, session in self.sessions.items() if session.expires_at > now}

    def resolve(self, token):
        self._expire()
        if token not in self.sessions:
            raise ValueError("Please log into a synthetic account")
        return self.sessions[token]

    def logout(self, token):
        self.sessions.pop(token, None)

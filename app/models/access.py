"""Deployment-local users, revocable opaque sessions and versioned settings."""
from app.extensions import db


class User(db.Model):
    __tablename__ = 'app_user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False, unique=True)
    display_name = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(24), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.Integer, nullable=False)


class AuthSession(db.Model):
    __tablename__ = 'auth_session'
    token_hash = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('app_user.id'), nullable=True, index=True)
    csrf_token = db.Column(db.String(64), nullable=False)
    expires_at = db.Column(db.Integer, nullable=False, index=True)


class AccessState(db.Model):
    __tablename__ = 'access_state'
    id = db.Column(db.Integer, primary_key=True)
    initialized = db.Column(db.Boolean, nullable=False, default=False)
    lock_version = db.Column(db.Integer, nullable=False, default=0)


class SystemSettings(db.Model):
    __tablename__ = 'system_settings'
    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    payload = db.Column(db.JSON, nullable=False)


class LoginAttempt(db.Model):
    """A bounded per-name throttle also applies to names that do not exist."""
    __tablename__ = 'login_attempt'
    key = db.Column(db.String(64), primary_key=True)
    failures = db.Column(db.Integer, nullable=False, default=0)
    window_start = db.Column(db.Integer, nullable=False)

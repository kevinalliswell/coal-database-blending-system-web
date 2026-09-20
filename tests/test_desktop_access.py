import os


def test_persistent_secret_survives_transport_rotation(tmp_path):
    from desktop.runtime import persistent_app_secret
    first = persistent_app_secret(tmp_path / '用户数据')
    assert len(first) == 64
    assert persistent_app_secret(tmp_path / '用户数据') == first
    assert persistent_app_secret(tmp_path / '其他数据') != first
    if os.name != 'nt':  # Windows protects the containing user profile with ACLs.
        assert (tmp_path / '用户数据' / '.app-secret').stat().st_mode & 0o077 == 0


def test_invalid_secret_is_not_silently_replaced(tmp_path):
    import pytest
    from desktop.runtime import persistent_app_secret
    secret = tmp_path / '.app-secret'
    secret.write_text('damaged', encoding='ascii')
    with pytest.raises(RuntimeError, match='密钥'):
        persistent_app_secret(tmp_path)
    assert secret.read_text() == 'damaged'


def test_transport_marker_only_exists_after_token_validation():
    from desktop.runtime import TokenMiddleware
    seen = []
    wrapped = TokenMiddleware(lambda environ, start: seen.append(environ) or [], 'a' * 64)
    wrapped({'HTTP_X_CBOS_TOKEN': 'wrong'}, lambda *args: None)
    assert seen == []
    wrapped({'HTTP_X_CBOS_TOKEN': 'a' * 64}, lambda *args: None)
    assert seen[0]['cbos.transport_authenticated'] is True


def test_data_lock_refuses_running_backend_and_releases_on_exit(tmp_path):
    import pytest
    from desktop.runtime import exclusive_data_lock
    with exclusive_data_lock(tmp_path):
        with pytest.raises(RuntimeError, match='关闭'):
            with exclusive_data_lock(tmp_path):
                raise AssertionError('must not acquire active backend lock')
    with exclusive_data_lock(tmp_path):
        pass


def test_recovery_requires_existing_database_and_user_and_revokes_sessions(tmp_path):
    import pytest
    from app import create_app
    from app.extensions import db
    from app.models.access import AuthSession, User
    from app.services.access_service import create_initial_admin
    from desktop.runtime import reset_local_password
    with pytest.raises(ValueError, match='现有'):
        reset_local_password(tmp_path, 'missing', 'Newpassword123!')
    app = create_app('production', config_overrides={'TESTING': True, 'DATA_DIR': str(tmp_path),
        'UPLOAD_FOLDER': str(tmp_path / 'uploads'), 'SQLALCHEMY_DATABASE_URI': f'sqlite:///{tmp_path / "coal_system.db"}'})
    with app.app_context():
        db.create_all()
        user = create_initial_admin('admin', 'Testpassword123!')
        db.session.add(AuthSession(token_hash='x'*64, user_id=user.id, csrf_token='x'*32, expires_at=9999999999))
        db.session.commit()
    with pytest.raises(ValueError, match='不存在'):
        reset_local_password(tmp_path, 'missing', 'Newpassword123!')
    reset_local_password(tmp_path, 'admin', 'Newpassword123!')
    with app.app_context():
        from werkzeug.security import check_password_hash
        db.session.expire_all()
        assert check_password_hash(db.session.query(User).one().password_hash, 'Newpassword123!')
        assert db.session.query(AuthSession).count() == 0
        db.session.remove(); db.engine.dispose()


def test_reset_cli_disallows_password_argument_and_prompts_twice(tmp_path, monkeypatch, capsys):
    import pytest
    from desktop.backend_entry import main
    from desktop import runtime
    monkeypatch.setenv('CBOS_DESKTOP_DATA_DIR', str(tmp_path))
    monkeypatch.setattr('sys.argv', ['cbos-backend', '--reset-password', 'admin', '--data-dir', str(tmp_path), '--password', 'leaked'])
    with pytest.raises(SystemExit):
        main()
    assert 'leaked' not in capsys.readouterr().err
    monkeypatch.setattr('sys.argv', ['cbos-backend', '--reset-password', 'admin', '--data-dir', str(tmp_path)])
    calls = []
    monkeypatch.setattr('getpass.getpass', lambda prompt: calls.append(prompt) or 'Newpassword123!')
    monkeypatch.setattr(runtime, 'reset_local_password', lambda *args: None)
    (tmp_path / 'coal_system.db').write_bytes(b'existing')
    assert main() == 0
    assert len(calls) == 2
    assert 'Newpassword123!' not in capsys.readouterr().out

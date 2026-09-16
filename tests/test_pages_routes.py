from app import create_app
from app.extensions import db
import app.routes.pages as pages


def test_spa_assets_are_served_with_windows_relative_paths(tmp_path, monkeypatch):
    dist_dir = tmp_path / "dist"
    asset_dir = dist_dir / "assets"
    asset_dir.mkdir(parents=True)
    (asset_dir / "app.js").write_text("console.log('ok');", encoding="utf-8")
    (dist_dir / "index.html").write_text("<div id='root'></div>", encoding="utf-8")

    app = create_app(config_overrides={
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        "DATA_DIR": str(tmp_path),
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "SPA_DIST_DIR": str(dist_dir),
    })

    with app.app_context():
        db.drop_all()
        db.create_all()

    monkeypatch.setattr(pages.os.path, "relpath", lambda *_args, **_kwargs: r"assets\app.js")

    response = app.test_client().get("/assets/app.js")

    assert response.status_code == 200
    # Python reads OS MIME associations; Windows may use this legacy JS type.
    assert response.mimetype in {"text/javascript", "application/javascript"}
    assert response.get_data(as_text=True) == "console.log('ok');"

    with app.app_context():
        db.session.remove()
        db.drop_all()

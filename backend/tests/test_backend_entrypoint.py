from backend.app.main import app as canonical_app
from backend.main import app as compatibility_app


def test_backend_main_exports_canonical_application():
    assert compatibility_app is canonical_app

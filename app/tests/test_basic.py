from app import create_app


def test_app_creates_successfully():
    app = create_app()
    assert app is not None
    assert app.name == "app"

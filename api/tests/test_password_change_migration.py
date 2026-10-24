from sqlalchemy import inspect

from app.db import engine


def test_users_track_required_password_changes_and_token_invalidation():
    columns = {column["name"]: column for column in inspect(engine).get_columns("users")}

    assert columns["must_change_password"]["nullable"] is False
    assert columns["must_change_password"]["default"] is None
    assert columns["refresh_token_invalidated_at"]["nullable"] is True

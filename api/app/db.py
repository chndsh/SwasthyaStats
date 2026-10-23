from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)


@event.listens_for(engine, "connect")
def on_connect(dbapi_connection, connection_record):
    try:
        with dbapi_connection.cursor() as cur:
            cur.execute("SET SESSION app.current_user_id = '-1'")
        if hasattr(dbapi_connection, "autocommit") and not dbapi_connection.autocommit:
            dbapi_connection.commit()
    except Exception:
        pass


@event.listens_for(engine, "reset")
def on_reset(dbapi_connection, connection_record, reset_state=None):
    # Called when connection is returned to pool
    if dbapi_connection is None:
        return
    try:
        with dbapi_connection.cursor() as cur:
            cur.execute("SET SESSION app.current_user_id = '-1'")
        if hasattr(dbapi_connection, "autocommit") and not dbapi_connection.autocommit:
            dbapi_connection.commit()
    except Exception:
        pass


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def set_rls_user_id(db: Session, user_id: int):
    """Sets local RLS user_id for current transaction."""
    db.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"),
        {"uid": str(user_id)},
    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

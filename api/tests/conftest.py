import os
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("API_SECRET_KEY", "test-secret-key")
os.environ.setdefault("PASSWORD_ENCRYPTION_KEY", "test-password-key-32-bytes-minimum")

from app.db import Base
from app.models import CollectorConfigState


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    db = TestingSessionLocal()
    db.add(CollectorConfigState(id=1, active_config_version=1, pending_reload=False, updated_by="test"))
    db.commit()
    try:
        yield db
    finally:
        db.close()

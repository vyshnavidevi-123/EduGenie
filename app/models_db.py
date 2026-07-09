from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    history = relationship("QueryLog", back_populates="user", cascade="all, delete-orphan")


class QueryLog(Base):
    __tablename__ = "query_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    feature = Column(String(30), nullable=False)  # ask | explain | quiz | summarize | learning_path
    input_text = Column(Text, nullable=False)
    output_source = Column(String(30), nullable=False)  # gemini | local-lamini
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="history")

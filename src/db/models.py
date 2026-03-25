import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.core.config import settings


class Base(DeclarativeBase):
    """Базовий клас для всіх моделей БД."""

    pass


class Document(Base):
    """Модель документа для RAG системи."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_file: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    doc_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Зв'язки
    pages: Mapped[list["Page"]] = relationship(
        "Page", back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, title='{self.title}')>"


class Page(Base):
    """Модель сторінки документа."""

    __tablename__ = "pages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Зв'язки
    document: Mapped["Document"] = relationship("Document", back_populates="pages")
    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk", back_populates="page", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Page(id={self.id}, document_id={self.document_id}, page={self.page_number})>"


class Chunk(Base):
    """Модель шматка тексту (чанка) з його векторним представленням."""

    __tablename__ = "chunks"
    __table_args__ = (
        Index(
            "idx_chunks_content_fts",
            func.to_tsvector("simple", func.lower(Column("content", Text))),
            postgresql_using="gin",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pages.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Vector | None] = mapped_column(Vector(settings.CHUNK_SIZE))
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    meta_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Зв'язки
    page: Mapped["Page"] = relationship("Page", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<Chunk(id={self.id}, page_id={self.page_id}, index={self.chunk_index})>"

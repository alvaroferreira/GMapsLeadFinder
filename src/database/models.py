"""Modelos SQLAlchemy para persistencia de dados."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class para todos os modelos."""
    pass


class Business(Base):
    """Modelo principal para negocios/leads."""

    __tablename__ = "businesses"

    # Identificacao (Google Place ID)
    id: str = Column(String(255), primary_key=True)
    name: str = Column(String(255), nullable=False, index=True)
    formatted_address: Optional[str] = Column(Text)
    latitude: Optional[float] = Column(Float)
    longitude: Optional[float] = Column(Float)

    # Tipos e Status
    place_types: Optional[list] = Column(JSON, default=list)
    business_status: str = Column(String(50), default="OPERATIONAL")

    # Contactos
    phone_number: Optional[str] = Column(String(50))
    international_phone: Optional[str] = Column(String(50))
    website: Optional[str] = Column(String(500))
    google_maps_url: Optional[str] = Column(String(500))

    # Dados Enriquecidos - Contacto
    email: Optional[str] = Column(String(255))
    emails_scraped: Optional[list] = Column(JSON, default=list)
    social_linkedin: Optional[str] = Column(String(500))
    social_facebook: Optional[str] = Column(String(500))
    social_instagram: Optional[str] = Column(String(500))
    social_twitter: Optional[str] = Column(String(500))

    # Dados Enriquecidos - Decisores
    decision_makers: Optional[list] = Column(JSON, default=list)

    # Metadata de Enrichment
    enrichment_status: str = Column(String(20), default="pending", nullable=False)
    enrichment_error: Optional[str] = Column(Text)
    enriched_at: Optional[datetime] = Column(DateTime)

    # Metricas
    rating: Optional[float] = Column(Float)
    review_count: int = Column(Integer, default=0)
    price_level: Optional[int] = Column(Integer)

    # Analise
    has_website: bool = Column(Boolean, default=False)
    has_photos: bool = Column(Boolean, default=False)
    photo_count: int = Column(Integer, default=0)

    # Lead Management
    lead_score: int = Column(Integer, default=0, index=True)
    lead_status: str = Column(String(20), default="new", index=True, nullable=False)
    notes: Optional[str] = Column(Text)
    tags: Optional[list] = Column(JSON, default=list)

    # Timestamps
    first_seen_at: datetime = Column(DateTime, default=func.now(), nullable=False)
    last_updated_at: datetime = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    last_search_query: Optional[str] = Column(String(500))
    data_expires_at: Optional[datetime] = Column(DateTime)

    # Notion Integration
    notion_page_id: Optional[str] = Column(String(100))
    notion_synced_at: Optional[datetime] = Column(DateTime)

    # Relationships
    snapshots = relationship("BusinessSnapshot", back_populates="business", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_location", "latitude", "longitude"),
        Index("idx_lead_filter", "lead_status", "lead_score"),
        Index("idx_first_seen", "first_seen_at"),
        Index("idx_enrichment", "enrichment_status", "has_website"),
        Index("idx_score_status", "lead_score", "lead_status"),
        Index("idx_website_score", "has_website", "lead_score"),
    )

    def __repr__(self) -> str:
        return f"<Business(id={self.id}, name={self.name}, score={self.lead_score})>"


class SearchHistory(Base):
    """Historico de pesquisas realizadas."""

    __tablename__ = "search_history"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    query_type: str = Column(String(20))  # "text" ou "nearby"
    query_params: Optional[dict] = Column(JSON)
    results_count: int = Column(Integer, default=0)
    new_businesses_count: int = Column(Integer, default=0)
    api_calls_made: int = Column(Integer, default=0)
    executed_at: datetime = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("idx_search_date", "executed_at"),
    )

    def __repr__(self) -> str:
        return f"<SearchHistory(id={self.id}, type={self.query_type}, results={self.results_count})>"


class BusinessSnapshot(Base):
    """Snapshots historicos de negocios para tracking de mudancas."""

    __tablename__ = "business_snapshots"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    business_id: str = Column(String(255), ForeignKey("businesses.id"), nullable=False)
    snapshot_data: Optional[dict] = Column(JSON)
    rating_at_time: Optional[float] = Column(Float)
    review_count_at_time: Optional[int] = Column(Integer)
    captured_at: datetime = Column(DateTime, default=func.now())

    # Relationship
    business = relationship("Business", back_populates="snapshots")

    __table_args__ = (
        Index("idx_snapshot_business", "business_id", "captured_at"),
    )

    def __repr__(self) -> str:
        return f"<BusinessSnapshot(id={self.id}, business_id={self.business_id})>"


class TrackedSearch(Base):
    """Pesquisas configuradas para execucao automatica."""

    __tablename__ = "tracked_searches"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    name: str = Column(String(100), nullable=False)
    query_type: str = Column(String(20))
    query_params: Optional[dict] = Column(JSON)
    is_active: bool = Column(Boolean, default=True)
    interval_hours: int = Column(Integer, default=24)
    last_run_at: Optional[datetime] = Column(DateTime)
    next_run_at: Optional[datetime] = Column(DateTime)
    created_at: datetime = Column(DateTime, default=func.now())

    # Configuracoes de notificacao
    notify_on_new: bool = Column(Boolean, default=True)
    notify_threshold_score: int = Column(Integer, default=50)

    # Estatisticas de execucao
    total_runs: int = Column(Integer, default=0)
    total_new_found: int = Column(Integer, default=0)
    last_new_count: int = Column(Integer, default=0)

    # Relationships
    logs = relationship("AutomationLog", back_populates="tracked_search", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_tracked_active", "is_active", "next_run_at"),
    )

    def __repr__(self) -> str:
        return f"<TrackedSearch(id={self.id}, name={self.name}, active={self.is_active})>"


class AutomationLog(Base):
    """Log de execucoes automaticas de pesquisas."""

    __tablename__ = "automation_logs"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    tracked_search_id: int = Column(Integer, ForeignKey("tracked_searches.id"), nullable=False)
    executed_at: datetime = Column(DateTime, default=func.now())
    total_found: int = Column(Integer, default=0)
    new_found: int = Column(Integer, default=0)
    high_score_found: int = Column(Integer, default=0)
    duration_seconds: float = Column(Float, default=0.0)
    status: str = Column(String(20), default="success")
    error_message: Optional[str] = Column(Text)

    # Relationship
    tracked_search = relationship("TrackedSearch", back_populates="logs")

    __table_args__ = (
        Index("idx_automation_log_search", "tracked_search_id", "executed_at"),
    )

    def __repr__(self) -> str:
        return f"<AutomationLog(id={self.id}, search_id={self.tracked_search_id}, new={self.new_found})>"


class Notification(Base):
    """Notificacoes para novos leads de alto score."""

    __tablename__ = "notifications"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    type: str = Column(String(50), default="new_lead")
    title: str = Column(String(255), nullable=False)
    message: Optional[str] = Column(Text)
    business_id: Optional[str] = Column(String(255), ForeignKey("businesses.id"))
    tracked_search_id: Optional[int] = Column(Integer, ForeignKey("tracked_searches.id"))
    is_read: bool = Column(Boolean, default=False)
    created_at: datetime = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("idx_notification_unread", "is_read", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, type={self.type}, read={self.is_read})>"


class IntegrationConfig(Base):
    """Configuracoes de integracoes externas (Notion, etc)."""

    __tablename__ = "integration_configs"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    service: str = Column(String(50), unique=True, nullable=False)  # "notion"
    api_key: Optional[str] = Column(String(500))
    config: Optional[dict] = Column(JSON)  # {database_id, workspace_name, etc}
    is_active: bool = Column(Boolean, default=False)
    last_sync_at: Optional[datetime] = Column(DateTime)
    created_at: datetime = Column(DateTime, default=func.now())
    updated_at: datetime = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<IntegrationConfig(service={self.service}, active={self.is_active})>"


# Lead status options
LEAD_STATUSES = ["new", "contacted", "qualified", "converted", "rejected"]

# Enrichment status options
ENRICHMENT_STATUSES = ["pending", "in_progress", "completed", "failed", "skipped", "no_website"]

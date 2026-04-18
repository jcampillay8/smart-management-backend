# src/models.py
import enum
import uuid
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Table, Column, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import BaseModel, metadata
from src.config import settings

# --- Relaciones de Autenticación (REQUERIDAS) ---
from src.authentication.models import (
    UserSessionHistory, 
    RefreshToken, 
    EmailConfirmationToken, 
    PasswordResetToken
)
from src.inventory.models import Categoria, Producto, Bodega, ProductoBodega
from src.operations.models import RegistroStock, Evento, EventoProducto
from src.sales.models import Receta, RecetaIngrediente, VentaReceta
from src.ai_management.models import LLMRequestLog

# NOTA: Los modelos de ai_manage y common_errors se comentan para priorizar Auth.
# Una vez estable la autenticación, se irán integrando.

class RemoveBaseFieldsMixin:
    created_at = None
    updated_at = None
    is_deleted = None
    
class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"

class AppRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"
    SUPERVISOR = "supervisor"

# Tabla intermedia con esquema explícito
user_chat = Table(
    "user_chat",
    metadata,
    Column("user_id", ForeignKey(f"{settings.DB_SCHEMA}.users.id"), primary_key=True),
    Column("chat_id", ForeignKey(f"{settings.DB_SCHEMA}.chats.id"), primary_key=True),
    schema=settings.DB_SCHEMA
)

class User(BaseModel):
    __tablename__ = "users"
    __table_args__ = (
        Index("idx_user_email_username", "email", "username"),
        {'schema': settings.DB_SCHEMA}
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(150), unique=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password: Mapped[str] = mapped_column(String(128))
    
    # Onboarding
    first_name: Mapped[str] = mapped_column(String(150), default="")
    last_name: Mapped[str] = mapped_column(String(150), default="")
    occupation: Mapped[str] = mapped_column(String(150), nullable=True)
    native_language: Mapped[str] = mapped_column(String(50), server_default="Spanish")
    has_completed_onboarding: Mapped[bool] = mapped_column(Boolean, default=False)
    
    user_image: Mapped[str] = mapped_column(String(1048), nullable=True)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    has_accepted_terms: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relaciones Auth
    session_history: Mapped[List["UserSessionHistory"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    email_confirmation_tokens: Mapped[List["EmailConfirmationToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    password_reset_tokens: Mapped[List["PasswordResetToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    chats: Mapped[List["Chat"]] = relationship(secondary=user_chat, back_populates="users")
    messages: Mapped[List["Message"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    # Nuevo: Role basado en la migración de tu amigo
    role: Mapped[AppRole] = mapped_column(
        Enum(AppRole, inherit_schema=True), 
        server_default=AppRole.USER, 
        nullable=False
    )

    # Relaciones de Inventario (Nuevas)
    permisos_otorgados: Mapped[List["PermisoMerma"]] = relationship(
        "PermisoMerma", 
        foreign_keys="[PermisoMerma.user_id]", 
        back_populates="user"
    )

    llm_requests: Mapped[List["LLMRequestLog"]] = relationship("LLMRequestLog", back_populates="user", cascade="all, delete-orphan")

    def __str__(self):
        return f"{self.username}"

class PermisoMerma(BaseModel):
    __tablename__ = "permisos_merma"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.users.id", ondelete="CASCADE"))
    otorgado_por: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="permisos_otorgados")
    autorizador: Mapped["User"] = relationship("User", foreign_keys=[otorgado_por])

class Message(BaseModel):
    __tablename__ = "messages"
    __table_args__ = (
        Index("idx_message_user_id", "user_id"),
        Index("idx_message_chat_id", "chat_id"),
        {'schema': settings.DB_SCHEMA}
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole, inherit_schema=True), nullable=False)
    content: Mapped[str] = mapped_column(String(5000))
    
    chat_id: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.chats.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.users.id"))
    
    chat: Mapped["Chat"] = relationship(back_populates="messages")
    user: Mapped["User"] = relationship(back_populates="messages")

    def __str__(self):
        return f"{self.role.upper()}: {self.content[:40]}..."

class Chat(BaseModel):
    __tablename__ = "chats"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[int] = mapped_column(primary_key=True)
    guid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(150))
    system_prompt: Mapped[str] = mapped_column(String(2000))

    users: Mapped[List["User"]] = relationship(secondary=user_chat, back_populates="chats")
    messages: Mapped[List["Message"]] = relationship(back_populates="chat")
    
    is_tts_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    selected_voice: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    def __str__(self):
        return f"{self.title}"

class ReadStatus(RemoveBaseFieldsMixin, BaseModel):
    __tablename__ = "read_status"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    last_read_message_id: Mapped[int] = mapped_column(nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.users.id"))
    chat_id: Mapped[int] = mapped_column(ForeignKey(f"{settings.DB_SCHEMA}.chats.id")) 

    chat: Mapped["Chat"] = relationship()
    user: Mapped["User"] = relationship()

class ConfiguracionRestaurante(BaseModel):
    __tablename__ = "configuracion_restaurante"
    __table_args__ = ({'schema': settings.DB_SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    logo_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
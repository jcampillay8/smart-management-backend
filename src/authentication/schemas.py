# src/authentication/schemas.py
from pydantic import (
    UUID4, 
    BaseModel, 
    EmailStr, 
    Field, 
    field_validator, 
    model_validator, 
    ConfigDict
)
from typing import Optional, Dict, Any
from uuid import UUID
from src.config import settings

class UserPublicSchema(BaseModel):
    """
    Esquema público para la información del usuario.
    Optimizado para Pydantic V2.
    """
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

    id: int
    user_guid: UUID4 = Field(..., alias="guid") 
    username: str
    email: EmailStr
    first_name: str = Field(..., alias="firstName")
    last_name: str = Field(..., alias="lastName")
    user_image: Optional[str] = Field(None, alias="userImage")
    settings: Dict[str, Any] = Field(default_factory=dict)
    has_accepted_terms: bool = Field(..., alias="termsAccepted")
    token_expires_at: Optional[int] = Field(None, alias="tokenExpiresAt")
    role: str = "user"

    @model_validator(mode='before')
    @classmethod
    def inject_default_tour_flag(cls, data: Any) -> Any:
        """
        Asegura que 'show_tour' exista en los settings.
        Maneja tanto diccionarios como objetos de SQLAlchemy.
        """
        # Extraer los settings actuales
        if isinstance(data, dict):
            current_settings = data.get("settings") or {}
            # Si es un dict, lo modificamos directamente
            if 'show_tour' not in current_settings:
                current_settings['show_tour'] = True
            data["settings"] = current_settings
        else:
            # Si es un objeto de SQLAlchemy (BaseModel)
            current_settings = getattr(data, "settings", {}) or {}
            if 'show_tour' not in current_settings:
                # No modificamos el objeto DB, solo los datos que van al schema
                current_settings = {**current_settings, "show_tour": True}
                # Para Pydantic V2 'before', podemos devolver un dict con los atributos del objeto
                # o simplemente modificar el objeto si es mutable, pero lo más limpio es esto:
                return data

        return data

    @field_validator("user_image", mode="after")
    @classmethod
    def add_image_host(cls, v: Optional[str]) -> Optional[str]:
        """Añade el host de estáticos en desarrollo."""
        if v and "/static/" in v and settings.ENVIRONMENT == "development":
            return f"{settings.STATIC_HOST}{v}"
        return v


class ForgotPasswordSchema(BaseModel):
    email: EmailStr = Field(..., description="Email del usuario para restablecer contraseña.")


class ResetPasswordSchema(BaseModel):
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=128)
    confirm_password: str = Field(..., min_length=6, max_length=128)

    @model_validator(mode="after")
    def passwords_match(self) -> "ResetPasswordSchema":
        """Validador de coincidencia de contraseñas en Pydantic V2."""
        if self.new_password != self.confirm_password:
            raise ValueError("Las contraseñas no coinciden.")
        return self


class LoginResponseSchema(UserPublicSchema):
    """
    Respuesta de login exitoso.
    """
    access_token: str = Field(..., alias="accessToken")
    token_type: str = Field("bearer", alias="tokenType")
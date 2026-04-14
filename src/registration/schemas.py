# src/registration/schemas.py

from pydantic import BaseModel, EmailStr, Field

class UserRegisterSchema(BaseModel):
    email: EmailStr
    username: str = Field(max_length=150)
    password: str = Field(min_length=6, max_length=128)
    first_name: str = Field(max_length=150)
    last_name: str = Field(max_length=150)
    terms_accepted: bool = Field(..., description="User's acceptance of terms and conditions")
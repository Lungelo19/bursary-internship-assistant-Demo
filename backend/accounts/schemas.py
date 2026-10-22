from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class RegisterRequest(BaseModel):
    full_name: str = Field(
        min_length=2,
        max_length=100,
    )
    email: str
    password: str = Field(
        min_length=6,
        max_length=128,
    )

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        value = value.strip().lower()

        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("Invalid email address.")

        return value


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        return value.strip().lower()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None


class StudentProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    province: Optional[str] = None
    education_level: Optional[str] = None
    pass_type: Optional[str] = None

    subjects: Dict[str, float] = Field(
        default_factory=dict
    )

    interests: List[str] = Field(
        default_factory=list
    )

    preferred_institutions: List[str] = Field(
        default_factory=list
    )

    funding_required: bool = True

    @field_validator("subjects")
    @classmethod
    def validate_subject_marks(
        cls,
        subjects: Dict[str, float],
    ) -> Dict[str, float]:

        for subject, mark in subjects.items():
            if mark < 0 or mark > 100:
                raise ValueError(
                    f"{subject}: marks must be between 0 and 100."
                )

        return subjects


class StudentProfileResponse(BaseModel):
    user_id: int
    email: str
    full_name: Optional[str] = None
    province: Optional[str] = None
    education_level: Optional[str] = None
    pass_type: Optional[str] = None
    subjects: Dict[str, float]
    interests: List[str]
    preferred_institutions: List[str]
    funding_required: bool
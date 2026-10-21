from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ProgrammeRecommendationRequest(BaseModel):
    subjects: dict[str, float] = Field(
        ...,
        description="Student subjects and percentage marks.",
        examples=[
            {
                "English": 67,
                "Mathematics": 72,
                "Physical Sciences": 63,
                "Life Sciences": 70,
                "Geography": 61,
                "isiZulu": 75,
                "Life Orientation": 80,
            }
        ],
    )
    pass_type: Literal[
        "degree",
        "diploma",
        "higher_certificate",
    ]
    interests: list[str] = Field(default_factory=list)
    preferred_institutions: list[str] = Field(default_factory=list)
    preferred_study_levels: list[str] = Field(default_factory=list)
    interest_limit: int = Field(default=10, ge=0, le=50)
    limit: int = Field(default=20, ge=1, le=100)
    include_gaps: bool = False
    include_uncertain: bool = False

    @field_validator("subjects")
    @classmethod
    def validate_subject_marks(cls, subjects):
        if not subjects:
            raise ValueError("At least one subject result is required.")

        cleaned = {}

        for subject, mark in subjects.items():
            subject = str(subject).strip()

            if not subject:
                raise ValueError("Subject names cannot be empty.")

            value = float(mark)

            if value < 0 or value > 100:
                raise ValueError(
                    f"{subject}: marks must be between 0 and 100."
                )

            cleaned[subject] = value

        return cleaned

    @field_validator("interests", "preferred_institutions", "preferred_study_levels")
    @classmethod
    def clean_string_lists(cls, values):
        return [
            str(value).strip()
            for value in values
            if str(value).strip()
        ]

from fastapi import APIRouter, HTTPException, Query

from app.programmes.matcher import recommend_programmes
from app.programmes.schemas import ProgrammeRecommendationRequest
from app.programmes.service import (
    get_programme_offering,
    list_campuses,
    list_career_directions,
    list_institutions,
    list_study_levels,
    search_programmes,
)


router = APIRouter(
    prefix="/programmes",
    tags=["Programmes"],
)


@router.get("")
def browse_programmes(
    search: str | None = Query(
        default=None,
        description="Programme name, code, institution, campus, or career keyword.",
    ),
    institution: str | None = Query(
        default=None,
        description="Institution code or institution name.",
    ),
    campus: str | None = Query(
        default=None,
        description="Campus code or campus name.",
    ),
    career: str | None = Query(
        default=None,
        description="CAO career direction.",
    ),
    study_level: str | None = Query(
        default=None,
        description="Exact CAO study-level label.",
    ),
    entry_term: str | None = Query(
        default=None,
        description="CAO entry term, for example 1 or 3.",
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
):
    return search_programmes(
        search=search,
        institution=institution,
        campus=campus,
        career=career,
        study_level=study_level,
        entry_term=entry_term,
        limit=limit,
        offset=offset,
    )


@router.get("/institutions")
def get_institutions():
    return {
        "items": list_institutions(),
    }


@router.get("/campuses")
def get_campuses(
    institution: str | None = Query(
        default=None,
        description="Optional institution code or name.",
    ),
):
    return {
        "items": list_campuses(
            institution=institution,
        ),
    }


@router.get("/career-directions")
def get_career_directions():
    return {
        "items": list_career_directions(),
    }


@router.get("/study-levels")
def get_study_levels():
    return {
        "items": list_study_levels(),
    }


@router.post("/recommend")
def get_recommendations(
    request: ProgrammeRecommendationRequest,
):
    return recommend_programmes(
        student_results=request.subjects,
        student_pass_type=request.pass_type,
        interests=request.interests,
        preferred_institutions=request.preferred_institutions,
        preferred_study_levels=(
            request.preferred_study_levels or None
        ),
        interest_limit=request.interest_limit,
        limit=request.limit,
        include_gaps=request.include_gaps,
        include_uncertain=request.include_uncertain,
    )


@router.get("/{offering_id}")
def get_programme_details(
    offering_id: int,
):
    programme = get_programme_offering(
        offering_id
    )

    if programme is None:
        raise HTTPException(
            status_code=404,
            detail="Programme offering not found.",
        )

    return programme

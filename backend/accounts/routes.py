import jwt

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from .database import init_database
from .schemas import (
    LoginRequest,
    RegisterRequest,
    StudentProfileResponse,
    StudentProfileUpdate,
    TokenResponse,
    UserResponse,
)
from .security import (
    create_access_token,
    decode_access_token,
)
from .service import (
    authenticate_user,
    create_user,
    get_student_profile,
    get_user_by_id,
    update_student_profile,
)


init_database()

auth_router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

profile_router = APIRouter(
    prefix="/profile",
    tags=["Student Profile"],
)

bearer_scheme = HTTPBearer(
    auto_error=False
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(
        bearer_scheme
    ),
):
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    try:
        user_id = decode_access_token(
            credentials.credentials
        )

    except (
        jwt.InvalidTokenError,
        ValueError,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={
                "WWW-Authenticate": "Bearer"
            },
        )

    user = get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists.",
        )

    return user


@auth_router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    request: RegisterRequest,
):
    user = create_user(
        email=request.email,
        password=request.password,
        full_name=request.full_name,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    token = create_access_token(
        user["id"]
    )

    return {
        "access_token": token,
        "token_type": "bearer",
    }


@auth_router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    request: LoginRequest,
):
    user = authenticate_user(
        request.email,
        request.password,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    return {
        "access_token": create_access_token(
            user["id"]
        ),
        "token_type": "bearer",
    }


@auth_router.get(
    "/me",
    response_model=UserResponse,
)
def me(
    current_user=Depends(
        get_current_user
    ),
):
    return current_user


@profile_router.get(
    "/me",
    response_model=StudentProfileResponse,
)
def profile_me(
    current_user=Depends(
        get_current_user
    ),
):
    profile = get_student_profile(
        current_user["id"]
    )

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Student profile not found.",
        )

    return profile


@profile_router.put(
    "/me",
    response_model=StudentProfileResponse,
)
def update_profile(
    request: StudentProfileUpdate,
    current_user=Depends(
        get_current_user
    ),
):
    return update_student_profile(
        current_user["id"],
        request,
    )
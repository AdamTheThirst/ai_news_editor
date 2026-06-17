from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """Return minimal application health status without internal details."""

    return {"status": "ok"}

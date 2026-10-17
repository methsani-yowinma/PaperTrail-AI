from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.concurrency import run_in_threadpool

from app.api.deps import get_container, get_current_user
from app.core.container import Container
from app.core.security import AuthUser
from app.schemas.api import AssessmentOut, InvestigationCreate, InvestigationOut, Page, ReportOut, VerifyResponse

router = APIRouter(prefix="/api/v1/investigations", tags=["investigations"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=InvestigationOut)
def create_investigation(
    body: InvestigationCreate, user: AuthUser = Depends(get_current_user), container: Container = Depends(get_container)
) -> InvestigationOut:
    inv = container.investigations.create(user.id, body)
    return container.investigations.to_out(inv)


@router.get("", response_model=Page[InvestigationOut])
def list_investigations(
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: AuthUser = Depends(get_current_user),
    container: Container = Depends(get_container),
) -> Page[InvestigationOut]:
    items, total = container.repo.list_investigations(user.id, query=q, limit=limit, offset=offset)
    return Page(items=[container.investigations.to_out(i) for i in items], total=total, limit=limit, offset=offset)


@router.get("/{investigation_id}", response_model=InvestigationOut)
def get_investigation(
    investigation_id: str, user: AuthUser = Depends(get_current_user), container: Container = Depends(get_container)
) -> InvestigationOut:
    return container.investigations.to_out(container.investigations.get(user.id, investigation_id))


@router.delete("/{investigation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_investigation(
    investigation_id: str, user: AuthUser = Depends(get_current_user), container: Container = Depends(get_container)
) -> Response:
    container.investigations.delete(user.id, investigation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{investigation_id}/verify", response_model=VerifyResponse)
async def verify_investigation(
    investigation_id: str, user: AuthUser = Depends(get_current_user), container: Container = Depends(get_container)
) -> VerifyResponse:
    """Run retrieval, assessment, citation validation and verdict aggregation (bounded, synchronous).

    Returns 200 with `assessment.status = "failed"` when retrieval worked but the claim could
    not be assessed (for example Gemini is not configured); retrieved passages are included
    as UNASSESSED and no verdict is produced.
    """
    container.rate_limiter.check(user.id, "verification", container.settings.rate_limit_verify_per_minute)
    inv, assessment = await run_in_threadpool(container.investigations.verify, user.id, investigation_id)
    return VerifyResponse(
        investigation=container.investigations.to_out(inv),
        assessment=container.investigations.assessment_out(user.id, assessment),
    )


@router.get("/{investigation_id}/evidence", response_model=AssessmentOut)
def get_latest_evidence(
    investigation_id: str, user: AuthUser = Depends(get_current_user), container: Container = Depends(get_container)
) -> AssessmentOut:
    assessment = container.investigations.latest_assessment(user.id, investigation_id)
    return container.investigations.assessment_out(user.id, assessment)


@router.get("/{investigation_id}/report", response_model=ReportOut)
def get_investigation_report(
    investigation_id: str, user: AuthUser = Depends(get_current_user), container: Container = Depends(get_container)
) -> ReportOut:
    return container.reports.for_investigation(user.id, investigation_id)

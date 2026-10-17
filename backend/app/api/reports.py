from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import get_container, get_current_user
from app.core.container import Container
from app.core.security import AuthUser
from app.schemas.api import Page, ReportListItem, ReportOut
from app.services.report_service import report_to_markdown

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("", response_model=Page[ReportListItem])
def list_reports(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: AuthUser = Depends(get_current_user),
    container: Container = Depends(get_container),
) -> Page[ReportListItem]:
    items, total = container.reports.list(user.id, limit, offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/{report_id}", response_model=ReportOut)
def get_report(
    report_id: str, user: AuthUser = Depends(get_current_user), container: Container = Depends(get_container)
) -> ReportOut:
    return container.reports.build(user.id, report_id)


@router.get("/{report_id}/export")
def export_report(
    report_id: str,
    format: Literal["markdown", "json"] = Query(default="markdown"),
    user: AuthUser = Depends(get_current_user),
    container: Container = Depends(get_container),
) -> Response:
    report = container.reports.build(user.id, report_id)
    slug = re.sub(r"[^a-z0-9]+", "-", report.title.lower()).strip("-")[:60] or "report"
    if format == "json":
        return Response(
            content=report.model_dump_json(indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="papertrail-{slug}.json"'},
        )
    return Response(
        content=report_to_markdown(report),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="papertrail-{slug}.md"'},
    )

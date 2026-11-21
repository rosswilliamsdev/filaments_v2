"""GET /api/health: the one unauthenticated API route."""

import logging

from django.db import DatabaseError, connection
from ninja import Router, Status

from schemas import ErrorDetail, HealthStatus

logger = logging.getLogger(__name__)

router = Router(tags=["health"])


@router.get("", auth=None, response={200: HealthStatus, 503: ErrorDetail})
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        logger.exception("Health check failed: database unavailable")
        return Status(503, ErrorDetail(detail="Database unavailable"))
    return Status(200, HealthStatus(status="ok"))

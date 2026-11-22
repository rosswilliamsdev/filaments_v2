"""The project's single NinjaAPI instance, mounted at /api/."""

import logging

from ninja import NinjaAPI

from api.filaments import router as filaments_router
from api.health import router as health_router
from api.tags import router as tags_router

logger = logging.getLogger(__name__)

api = NinjaAPI(title="Filaments v2 API", version="0.1.0")

api.add_router("/health", health_router)
api.add_router("/filaments", filaments_router)
api.add_router("/tags", tags_router)

SERVER_ERROR = "Something went wrong on the server. It has been logged."


@api.exception_handler(Exception)
def unexpected_error(request, exc):
    # Ninja matches handlers by the exception's MRO, so its own handlers for HttpError,
    # validation and auth errors still apply; this catches everything else.
    logger.exception("Unhandled error in %s %s", request.method, request.path)
    return api.create_response(request, {"detail": SERVER_ERROR}, status=500)

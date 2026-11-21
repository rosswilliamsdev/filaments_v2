"""The project's single NinjaAPI instance, mounted at /api/."""

from ninja import NinjaAPI

from api.health import router as health_router

api = NinjaAPI(title="Filaments v2 API", version="0.1.0")

api.add_router("/health", health_router)

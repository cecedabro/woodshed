"""Route modules aggregation.

Imported by ``main.py`` which includes each router on the FastAPI app.
"""

from app.routes.items import router as items_router
from app.routes.media import router as media_router
from app.routes.metronome import router as metronome_router
from app.routes.progress import router as progress_router
from app.routes.routines import router as routines_router
from app.routes.run import router as run_router
from app.routes.settings import router as settings_router
from app.routes.tuner import router as tuner_router

__all__ = [
    "items_router",
    "media_router",
    "metronome_router",
    "progress_router",
    "routines_router",
    "run_router",
    "settings_router",
    "tuner_router",
]

from fastapi import APIRouter, Depends
from .learnpress import router as learnpress_router
from .comments import router as comments_router
from .forms import router as forms_router
from .marketing import router as marketing_router
from .settings import router as settings_router
from .traders import router as traders_router
from app.dependencies.auth import get_current_admin

router = APIRouter(dependencies=[Depends(get_current_admin)])

router.include_router(learnpress_router, prefix="/admin/learnpress", tags=["Admin LearnPress"])
router.include_router(comments_router, prefix="/admin/comments", tags=["Admin Comments"])
router.include_router(forms_router, prefix="/admin/forms", tags=["Admin Forms"])
router.include_router(marketing_router, prefix="/admin/marketing", tags=["Admin Marketing"])
router.include_router(settings_router, prefix="/admin/settings", tags=["Admin Settings"])
router.include_router(traders_router, prefix="/admin/traders", tags=["Admin Traders"])

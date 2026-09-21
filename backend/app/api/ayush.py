from typing import List, Union
from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from app.services.ayush_normalizer_service import (
    AyushNormalizationResult,
    ayush_normalizer_service,
)

router = APIRouter(prefix="/ayush", tags=["ayush"])


class AyushNormalizeRequest(BaseModel):
    query: Union[str, List[str]] = Field(
        ...,
        examples=["Avipattikar Churna 3g", ["Ashwagandha Churna", "सूतशेखर रस"]],
        description="Single medication text or list of Ayurvedic drug strings to normalize.",
    )


class AyushNormalizeResponse(BaseModel):
    results: List[AyushNormalizationResult]


@router.post(
    "/normalize",
    response_model=AyushNormalizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Fuzzy match Ayurvedic drug text to official AFI & NAMASTE standard codes",
)
def normalize_ayush_entity(payload: AyushNormalizeRequest):
    if isinstance(payload.query, list):
        results = ayush_normalizer_service.normalize_list(payload.query)
    else:
        results = [ayush_normalizer_service.normalize(payload.query)]
    return AyushNormalizeResponse(results=results)

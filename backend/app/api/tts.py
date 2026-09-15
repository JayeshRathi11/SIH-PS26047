from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.nlp.tts.provider import tts_provider


router = APIRouter(tags=["tts"])


class TTSRequest(BaseModel):
    text: str
    language_code: str = "en"


@router.post("/api/tts")
def synthesize_speech(request: TTSRequest):
    audio = tts_provider.synthesize(
        text=request.text,
        language_code=request.language_code,
    )

    return Response(
        content=audio,
        media_type="audio/wav",
    )
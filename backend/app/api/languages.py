from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.language import LanguageResponse
from app.services.language_service import language_service

router = APIRouter(prefix="/languages", tags=["languages"])


@router.get("", response_model=List[LanguageResponse], status_code=status.HTTP_200_OK)
def get_supported_languages(db: Session = Depends(get_db)):
    return language_service.get_active_languages(db=db)

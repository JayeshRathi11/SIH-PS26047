from pydantic import BaseModel, ConfigDict, Field


class LanguageResponse(BaseModel):
    code: str
    name: str
    native_name: str

    model_config = ConfigDict(from_attributes=True)


class InterviewLanguageUpdate(BaseModel):
    language_code: str = Field(
        ...,
        min_length=2,
        max_length=10,
        description="Supported active language code (e.g. en, hi, mr)",
        examples=["mr"],
    )

    model_config = ConfigDict(extra="forbid")



class InterviewLanguageResponse(BaseModel):
    interview_id: int
    language_code: str
    name: str
    native_name: str

    model_config = ConfigDict(from_attributes=True)

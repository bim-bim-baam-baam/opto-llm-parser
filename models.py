from pydantic import BaseModel


class AnalysisResult(BaseModel):
    path: str
    package: str
    error_type: str
    description: str
    programming_language: str

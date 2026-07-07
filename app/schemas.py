from typing import List, Optional
from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class ExplainRequest(BaseModel):
    concept: str = Field(..., min_length=1, max_length=500)
    level: str = Field("beginner", description="beginner | intermediate | advanced")


class QuizRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500)
    num_questions: int = Field(5, ge=1, le=15)
    difficulty: str = Field("medium", description="easy | medium | hard")


class QuizQuestion(BaseModel):
    question: str
    options: List[str]
    answer_index: int
    explanation: str


class QuizResponse(BaseModel):
    topic: str
    questions: List[QuizQuestion]
    source: str


class SummarizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)
    length: str = Field("medium", description="short | medium | detailed")


class LearningPathRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500)
    current_level: str = Field("beginner", description="beginner | intermediate | advanced")
    goal: Optional[str] = Field(None, max_length=500)


class LearningPathStage(BaseModel):
    stage: str
    focus_areas: List[str]
    resources_to_seek: List[str]
    estimated_time: str


class LearningPathResponse(BaseModel):
    topic: str
    stages: List[LearningPathStage]
    source: str


class GenericTextResponse(BaseModel):
    result: str
    source: str

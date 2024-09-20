from pydantic import BaseModel,Field

class OutputType(BaseModel):
    answer: str
    is_relevant: str
    decision: str

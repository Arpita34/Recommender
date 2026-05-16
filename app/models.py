from pydantic import BaseModel, Field, field_validator
from typing import Literal, List

class Message(BaseModel):
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=4000)

class ChatRequest(BaseModel):
    messages: List[Message] = Field(min_length=1, max_length=20)

    @field_validator('messages')
    @classmethod
    def first_must_be_user(cls, v):
        if v and v[0].role != 'user':
            raise ValueError('First message must be from user')
        return v

class Recommendation(BaseModel):
    name: str
    url: str
    test_type: str

class ChatResponse(BaseModel):
    reply: str
    recommendations: List[Recommendation] = []
    end_of_conversation: bool = False

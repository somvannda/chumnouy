from pydantic import BaseModel


class HealthRead(BaseModel):
    status: str
    service: str
    version: str
    environment: str

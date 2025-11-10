from typing import Optional
from pydantic import BaseModel, field_validator

class borger(BaseModel):

    cpr: str
from typing import Literal, List
from pydantic import BaseModel, Field
from datetime import datetime

InitialElkResponseState = Literal["ongoing", "success", "busy", "failed"]


class InitialCallElkResponse(BaseModel):
    callid: str = Field(alias="id")
    created: datetime
    direction: Literal["incoming", "outgoing"]
    state: InitialElkResponseState
    from_nr: str = Field(alias="from")
    to_nr: str = Field(alias="to")


class Number(BaseModel):
    category: Literal["fixed", "mobile", "voip"]
    country: str
    expires: datetime
    number: str
    capabilities: List[str]
    cost: int
    active: Literal["yes", "no"]
    allocated: datetime
    id: str

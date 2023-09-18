from datetime import datetime
import logging
from typing import Tuple, List, Literal
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Request, status

import requests

from dearmep.config import Config

# Config

Config.load()
config = Config.get().telephony

whitelisted_ips: Tuple[str, ...] = config.provider.allowed_ips
auth: Tuple[str, str] = (
    config.provider.username,
    config.provider.password,
)

# Types
CallDirection = Literal["incoming", "outgoing"]
CallID = str
Cost = int
DateTime = datetime
Duration = int
FinalState = Literal["success", "failed", "busy"]
PhoneNumber = str


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


# will be loaded in function `startup`
phone_numbers: List[Number] = []

# Helpers


logger = logging.getLogger(__name__)


def get_numbers() -> List[Number]:
    """
    Fetches all available numbers to the account from 46elks.
    """

    response = requests.get(
        url="https://api.46elks.com/a1/numbers",
        auth=auth
    )
    if response.status_code != 200:
        logger.error(
            'Could not fetch numbers from 46elks. Response status: %s',
            response.status_code
        )
        return []

    numbers: List[Number] = [
        Number.parse_obj(number) for number in response.json().get('data')
    ]
    logger.info(f"Fetched {len(numbers)} phone numbers from 46elks.")

    return numbers


def verify_origin(request: Request):
    client_ip = None if request.client is None else request.client.host
    if client_ip not in whitelisted_ips:
        logger.debug(f"refusing {client_ip}, not a 46elks IP")
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            {
                "error": "You don't look like an elk.",
                "client_ip": client_ip,
            },
        )


# Routes

router = APIRouter(
    dependencies=[Depends(verify_origin)]
)


@router.on_event("startup")
async def startup():
    for number in get_numbers():
        phone_numbers.append(number)

    if len(phone_numbers) == 0:
        logger.error(
            "No phone numbers were fetched on startup. "
            "Please make sure you have configured your 46elks account."
        )


@router.get("/call")
def explorative_calls():

    response = requests.get(
        url="https://api.46elks.com/a1/numbers",
        auth=auth,
        data={}
    )
    response.raise_for_status()

    return {
        "response.status_code": response.status_code,
        "response.text": response.text
    }

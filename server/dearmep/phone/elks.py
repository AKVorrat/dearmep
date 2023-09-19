from datetime import datetime
import logging
from typing import Tuple, List, Literal
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Request, status

import requests

from dearmep.config import Config, Language

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
DateTime = datetime
PhoneNumber = str
InitialElkResponseState = Literal["ongoing", "success", "busy", "failed"]


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
    Fetches all available numbers of an account at 46elks.
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


class InitialCallElkResponse(BaseModel):
    id: str
    created: DateTime
    direction: Literal["incoming", "outgoing"]
    state: InitialElkResponseState
    from_nr: PhoneNumber
    to_nr: PhoneNumber


def initiate_call(
    dest_number: PhoneNumber,
    from_number: PhoneNumber,
    user_language: Language
) -> InitialElkResponseState:
    """ Initiate a Phone call via 46elks """

    response = requests.post(
        url="https://api.46elks.com/a1/calls",
        auth=auth,
        data={
            "to": dest_number,
            "from": from_number,
            "voice_start": f'https://a.jf.en.i.d.h.yq.de/{user_language}.mp3',
            "whenhangup": 'https://a.jf.en.i.d.h.yq.de/hangup',
            "timeout": 15
        }
    )

    response.raise_for_status()
    data: InitialCallElkResponse = response.json()

    if data.state == "failed":
        logger.warn(f"Call failed from our number: {from_number}")

    return data.state

# Routes


router = APIRouter(
    dependencies=[Depends(verify_origin)]
)


# TODO: deprecated, use lifespan
# https://fastapi.tiangolo.com/advanced/events/
@router.on_event("startup")
async def startup():
    for number in get_numbers():
        phone_numbers.append(number)

    if len(phone_numbers) == 0:
        logger.error(
            "No phone numbers were fetched on startup. "
            "Please make sure you have configured your 46elks account."
        )


@router.post("/voice-start/{language}")
async def voice_start(language: Language):
    """ Play mp3 to the called person in their language. """

    # TODO check if file for language exists, fallback to english
    prompt_path = f"/audio/experiments/46elks/connect-prompt.{language}.mp3"

    return {
        "play": f"{prompt_path}",
        "whenhangup": "call back gather info",
        "next": "callback connect call"
    }

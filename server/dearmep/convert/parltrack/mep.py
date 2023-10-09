from datetime import date
from io import BufferedReader
import json
import re
from typing import Any, Dict, Generator, Iterable, List, Union, cast

from countryguess import guess_country  # type: ignore[import]

from ...config import APP_NAME
from ...database.models import ContactDump, DestinationDump, \
    DestinationGroupDump, DumpableModels
from ...progress import BaseTaskFactory, FlexiBytesReader


TODAY = date.today()

CONTACT_MAP = {
    "Facebook": "facebook",
    "Fax": "fax",
    "Homepage": "web",
    "Instagram": "instagram",
    "Mail": "email",
    "Phone": "phone",
    "Twitter": "twitter",
}

LOCATION_MAP = {
    "Brussels": "brussels",
    "Strasbourg": "strasbourg",
}

NON_FILENAME_SAFE = re.compile(r"[^\w\d _-]")


def is_current(item: dict) -> bool:
    start = parse_date(item["start"])
    end = parse_date(item["end"])
    return start <= TODAY <= end


def parse_date(datestr: str) -> date:
    return date.fromisoformat(datestr[:10])


def get_group(
    id: str,
    **kwargs,
) -> Generator[DestinationGroupDump, None, str]:
    # Initialize "static variable" for tracking known groups. mypy doesn't like
    # this (yet, see <https://github.com/python/mypy/issues/2087>), hence the
    # ignores down below.
    get_group.__dict__.setdefault("known", {})

    if id not in get_group.known:  # type: ignore[attr-defined]
        new_group = DestinationGroupDump(
            id=id,
            **kwargs,
        )
        get_group.known[id] = new_group  # type: ignore[attr-defined]
        yield new_group

    return id


def constituency_to_group(const: Dict[str, str]) -> Dict[str, str]:
    return {
        "type": "party",
        # Parltrack has some parties in different capitalizations.
        "id": f"P:{const['party'].lower()}",
        "long_name": const["party"],
        "logo": f"{NON_FILENAME_SAFE.sub('_', const['party'])}.png",
    }


def group_to_group(group: Dict[str, str]) -> Dict[str, str]:
    return {
        "type": "parl_group",
        "id": f"G:{group['groupid']}",
        "short_name": group["groupid"],
        "long_name": group["Organization"],
        "logo": f"{NON_FILENAME_SAFE.sub('_', group['groupid'])}.png",
    }


def convert_contact(type: str, contact: str) -> str:
    # Parltrack uses phone/fax numbers starting with `00` instead of `+`.
    if type in ("Phone", "Fax") and contact.startswith("00"):
        return f"+{contact[2:]}"
    # No conversion necessary.
    return contact


def convert_person(raw_mep: Dict[str, Any]) -> Iterable[DumpableModels]:
    contacts = []
    # Top-level contacts like web links and email.
    for pt_key, dmep_key in CONTACT_MAP.items():
        for addr in raw_mep.get(pt_key, []):
            contacts.append(ContactDump(
                type=dmep_key,
                contact=addr,
            ))

    # Contacts that differ between Brussels & Strasbourg (e.g. phone).
    for pt_loc, dmep_loc in LOCATION_MAP.items():
        loc_addr = raw_mep.get("Addresses", {}).get(pt_loc, {})
        for pt_key, dmep_key in CONTACT_MAP.items():
            if pt_key in loc_addr:
                contacts.append(ContactDump(
                    type=dmep_key,
                    group=dmep_loc,
                    contact=convert_contact(pt_key, loc_addr[pt_key]),
                ))

    # Get the current group & constituency.
    group = next((
        group
        for group in cast(List[Dict[str, str]], raw_mep.get("Groups", []))
        if is_current(group)
    ), None)
    constituency = next((
        constituency
        for constituency in cast(
            List[Dict[str, str]], raw_mep.get("Constituencies", []))
        if is_current(constituency)
    ), None)

    # Look up group & constituency, add them to the dump on first appearance.
    groups: List[str] = []
    if group:
        group_id = yield from get_group(**group_to_group(group))
        groups.append(group_id)
    if constituency:
        group_id = yield from get_group(**constituency_to_group(constituency))
        groups.append(group_id)

    yield DestinationDump(
        id=raw_mep["UserID"],
        name=raw_mep["Name"]["full"],
        sort_name=f"{raw_mep['Name']['family']} {raw_mep['Name']['sur']}",
        country=guess_country(constituency["country"], attribute="iso2")
        if constituency else None,
        groups=groups,
        contacts=contacts,
        portrait=f"{raw_mep['UserID']}.jpg",
        name_audio=f"{raw_mep['UserID']}.mp3",
    )


def convert_meps(
    input: FlexiBytesReader,
    tf: BaseTaskFactory,
    *,
    include_inactive: bool = False,
    lz_compressed: bool = True,
) -> Iterable[DumpableModels]:
    dc_str = " and decompressing" if lz_compressed else ""
    with tf.create_task(f"reading{dc_str} input") as task:
        input.set_task(task)
        with input as input_stream:
            if lz_compressed:
                from ..lz import lz_decompressor
                src: Union[BufferedReader, Iterable[bytes]] \
                    = lz_decompressor(input_stream)
            else:
                src = input_stream
            # TODO: If src was a file-like, not a generator, we could skip this
            # .join() and use json.load() below to improve performance.
            json_bytes = b"".join(src)
    with tf.create_task("parsing JSON") as task:
        raw_meps = json.loads(json_bytes)
    with tf.create_task(
        f"converting to {APP_NAME} format",
        total=len(raw_meps),
    ) as task:
        for raw_mep in raw_meps:
            if include_inactive or raw_mep["active"] is True:
                yield from convert_person(raw_mep)
            task.advance()

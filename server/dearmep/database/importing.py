from __future__ import annotations
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Set, Type

from sqlmodel import SQLModel, Session

from ..convert.dump import DumpFormatException
from ..convert.image import image2blob
from .models import Contact, Destination, DestinationDump, DestinationGroup, \
    DestinationGroupDump, DestinationID, DumpableModels, SwayabilityImport


class Importer:
    def __init__(
        self,
        *,
        portrait_template: Optional[str] = None,
        fallback_portrait: Optional[Path] = None,
        logo_template: Optional[str] = None,
    ) -> None:
        self._dump2db: Dict[Type[DumpableModels], Callable] = {
            DestinationGroupDump: self._create_destination_group,
            DestinationDump: self._create_destination,
        }
        self._groups: Dict[str, DestinationGroup] = {}
        self._portrait_tpl = portrait_template
        self._logo_tpl = logo_template

        self._fallback_portrait = image2blob(
            "portrait", fallback_portrait,
            description="fallback portrait",
        ) if fallback_portrait else None

    def _create_destination(self, input: DestinationDump) -> Destination:
        contacts = list(
            Contact.from_orm(contact)
            for contact in input.contacts
        )
        groups = list(
            self._groups[group_id]
            for group_id in input.groups
        )
        dest = Destination.from_orm(input)
        dest.contacts = contacts
        dest.groups = groups

        if self._portrait_tpl:
            portrait_path = Path(self._portrait_tpl.format(
                id=dest.id,
                filename=input.portrait,
            ))
            if portrait_path.exists():
                dest.portrait = image2blob(
                    "portrait", portrait_path,
                    description=f"portrait for Destination {dest.id}",
                )
        if not dest.portrait and self._fallback_portrait:
            dest.portrait = self._fallback_portrait
        return dest

    def _create_destination_group(
        self,
        input: DestinationGroupDump,
    ) -> DestinationGroup:
        dg = DestinationGroup.from_orm(input)
        if dg.id in self._groups:
            raise DumpFormatException(f"duplicate group: {dg.id}")

        if self._logo_tpl:
            logo_path = Path(self._logo_tpl.format(
                id=dg.id,
                filename=input.logo,
                short_name=input.short_name,
                long_name=input.long_name,
            ))
            if logo_path.exists():
                dg.logo = image2blob(
                    "logo", logo_path,
                    description=f"logo of Group {dg.long_name}",
                )

        self._groups[dg.id] = dg
        return dg

    def import_dump(self, session: Session, objs: Iterable[DumpableModels]):
        self._groups = {}
        for obj in objs:
            obj_type = type(obj)
            if obj_type not in self._dump2db:
                raise DumpFormatException(f"unknown type: {obj_type}")
            model: SQLModel = self._dump2db[obj_type](obj)
            session.add(model)


def import_swayability(
    session: Session,
    objs: Iterable[SwayabilityImport],
    *,
    ignore_unknown: bool = False,
) -> Set[DestinationID]:
    """Import endorsement for Destinations.

    If `ignore_unknown` is set, IDs not found in the database will be ignored.
    A set of ignored IDs will be returned.
    """
    ignored: Set[DestinationID] = set()
    for obj in objs:
        dest = session.get(Destination, obj.id)
        if not dest:
            if ignore_unknown:
                ignored.add(obj.id)
                continue
            raise KeyError(f"no such Destination: {obj.id}")
        if obj.endorsement is not None:
            dest.base_endorsement = obj.endorsement
    return ignored

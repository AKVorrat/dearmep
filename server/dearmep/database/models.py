from datetime import datetime
import enum
from typing import Any, Dict, List, Optional, TypedDict, Union
from uuid import uuid4

from pydantic import UUID4, BaseModel
from sqlmodel import Column, Enum, Field, Relationship, SQLModel, TIMESTAMP, \
    and_, case, or_, func, text

from ..config import Config, ConfigNotLoaded
from ..models import CountryCode, Score


class _SchemaExtra(TypedDict):
    schema_extra: Dict[str, Any]


def _example(value: Any) -> _SchemaExtra:
    """Convenience function to add examples to SQLModel Fields."""
    return {
        "schema_extra": {
            "example": value,
        },
    }


class _SARelationshipKWArgs(TypedDict):
    sa_relationship_kwargs: Dict[str, str]


def _rel_join(join: str) -> _SARelationshipKWArgs:
    """Convenience function to disambiguate Relationship associations."""
    return {
        "sa_relationship_kwargs": {
            "primaryjoin": join,
        },
    }


def _contact_filter():
    predicates = [
        Contact.destination_id == Destination.id,  # usual join condition
    ]

    try:
        config = Config.get()
        tf = config.contact_timespan_filter
    except ConfigNotLoaded:
        tf = None

    if tf:
        # Convert the timespans to CASE expression tuples.
        today = func.current_date()
        cases = (
            (or_(*(
                and_(
                    today >= span.start,
                    today <= span.end,
                )
                for span in spans
            )), group)
            for group, spans in tf.timespans.items()
        )
        # Add the logic to the join.
        predicates.append(or_(
            Contact.type.not_in(tf.types),
            Contact.group == case(*cases, else_=tf.default),
        ))

    return and_(*predicates)


CONTACT_TYPES = (
    "email", "facebook", "fax", "instagram", "phone", "twitter", "web",
)


# These need to be individual lines, else (e.g. A = B = C = str) mypy won't
# recognize them as type aliases. This is intentional (but not very clever
# imho), see <https://github.com/python/mypy/issues/11858>.
BlobID = int
ContactID = int
DestinationID = str
DestinationGroupID = str


DEFAULT_BASE_ENDORSEMENT = 0.5


def auto_timestamp_column() -> Column:
    """A timestamp column that will default to whenever the row is created."""
    return Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ModifiedTimestampMixin(BaseModel):
    modified_at: Optional[datetime] = Field(
        sa_column=auto_timestamp_column(),
        description="Timestamp of last modification.",
    )


class Blob(SQLModel, ModifiedTimestampMixin, table=True):
    """A binary data object, e.g. an image or audio."""
    __tablename__ = "blobs"
    id: Optional[BlobID] = Field(
        None,
        primary_key=True,
        description="A (probably auto-generated) ID to uniquely identify this "
        "Blob.",
    )
    type: str = Field(
        index=True,
        description="A value to help organize Blobs into categories, e.g. "
        "`logo`, `portrait`, `name_audio` etc.",
        **_example("logo"),
    )
    mime_type: str = Field(
        description="The MIME type of this Blob.",
        **_example("image/svg+xml"),
    )
    name: str = Field(
        unique=True,
        description="The name of this Blob. Should be a valid file name.",
        **_example("dearmep.svg"),
    )
    description: Optional[str] = Field(
        None,
        description="An optional description of this Blob.",
        **_example("SVG logo of DearMEP"),
    )
    etag: UUID4 = Field(
        default_factory=uuid4,
        sa_column_kwargs={
            "onupdate": uuid4,
        },
        description="An opaque value that will change on every update.",
        **_example("d36bbbf4-0fd1-4ecf-a3e7-696521656a2f"),
    )
    data: bytes = Field(
        description="The actual binary content.",
    )


class ContactBase(SQLModel):
    """A single contact datum (e.g. website) belonging to a Destination."""
    type: str = Field(
        index=True,
        description="Which type of Contact this is. Can be any string that "
        "makes sense for the campaign. Some suggested values are: " +
        ", ".join(map(lambda k: f"`{k}`", CONTACT_TYPES)),
        **_example(CONTACT_TYPES[0]),
    )
    group: Optional[str] = Field(
        None,
        index=True,
        description="An optional identifier for grouping Contacts into "
        "categories. Can be used to identify `home` and `work` addresses, for "
        "example, or `brussels` and `strasbourg` phone numbers for Members of "
        "the European Parliament, etc.",
        **_example("brussels"),
    )
    contact: str = Field(
        description="The actual Contact address/number/URL/etc, depending on "
        "the `type`.",
        **_example("j.m.mierscheid@example.org"),
    )


class Contact(ContactBase, table=True):
    id: Optional[ContactID] = Field(
        None,
        primary_key=True,
        description="A (probably auto-generated) ID to uniquely identify this "
        "Contact.",
    )
    destination_id: Optional[DestinationID] = Field(
        foreign_key="destinations.id", index=True,
        description="The Destination this Contact belongs to.",
    )
    destination: "Destination" = Relationship(
        back_populates="contacts",
    )
    __tablename__ = "contacts"


class ContactDump(ContactBase):
    pass


class ContactListItem(ContactBase):
    pass


class DestinationGroupLink(SQLModel, table=True):
    """Association between a Destination and a DestinationGroup."""
    __tablename__ = "dest_group_link"
    destination_id: DestinationID = Field(
        foreign_key="destinations.id", primary_key=True,
    )
    group_id: DestinationGroupID = Field(
        foreign_key="dest_groups.id", primary_key=True,
    )


class DestinationBase(SQLModel):
    """A person (or entity) users are supposed to contact."""
    __tablename__ = "destinations"
    id: DestinationID = Field(
        primary_key=True,
        description="A unique string to identify this Destination.",
        **_example("36e04ddf-73e7-4af6-a8af-24556d610f6d"),
    )
    name: str = Field(
        description="The Destination’s name.",
        **_example("Jakob Maria MIERSCHEID"),
    )
    country: Optional[CountryCode] = Field(
        None,
        index=True,
        description="The country code associated with this Destination.",
        **_example("DE"),
    )


class Destination(DestinationBase, table=True):
    sort_name: str = Field(
        index=True,
        description="The Destination’s name, as used for sorting purposes. "
        "Usually, this will e.g. list the family name first, but the campaign "
        "is free to handle this as they please.",
        **_example("MIERSCHEID Jakob Maria"),
    )
    contacts: List[Contact] = Relationship(
        back_populates="destination",
        sa_relationship_kwargs={
            "primaryjoin": _contact_filter,
        }
    )
    groups: List["DestinationGroup"] = Relationship(
        back_populates="destinations", link_model=DestinationGroupLink,
    )
    portrait_id: Optional[BlobID] = Field(
        None,
        foreign_key="blobs.id",
        description="The portrait image of this Destination.",
    )
    portrait: Optional[Blob] = Relationship(
        **_rel_join("Destination.portrait_id==Blob.id"),
    )
    name_audio_id: Optional[BlobID] = Field(
        None,
        foreign_key="blobs.id",
        description="The spoken name of this Destination.",
    )
    name_audio: Optional[Blob] = Relationship(
        **_rel_join("Destination.name_audio_id==Blob.id"),
    )
    base_endorsement: Score = Field(
        index=True,
        default=DEFAULT_BASE_ENDORSEMENT,
        sa_column_kwargs={
            "server_default": text(str(DEFAULT_BASE_ENDORSEMENT)),
        },
        description="The manually defined base Endorsement value for this "
        "Destination.",
    )


class DestinationDump(DestinationBase):
    sort_name: str
    contacts: List[ContactDump] = []
    groups: List[DestinationGroupID] = []
    portrait: Optional[str]


class DestinationRead(DestinationBase):
    contacts: List[ContactListItem] = []
    groups: List["DestinationGroupListItem"] = []
    portrait: Optional[str] = Field(
        description="URL path to the portrait image of this Destination, if "
        "any is available.",
        **_example("/api/v1/blob/j.m.mierscheid.jpg"),
    )


class DestinationGroupBase(SQLModel):
    """A group to which Destinations may belong."""
    id: DestinationGroupID = Field(
        primary_key=True,
        description="An ID to uniquely identify this Group.",
    )
    type: str = Field(
        index=True,
        description="Which type of Group this is. Can be any string that "
        "makes sense for the campaign. Some suggested values are `parl_group` "
        "(parliamentary group, “Fraktion” in German), `party`, `committee`, "
        "`delegation` etc.",
        **_example("parl_group"),
    )
    short_name: Optional[str] = Field(
        None,
        description="The short name of this group.",
        **_example("S&D"),
    )
    long_name: str = Field(
        description="The long name of this group.",
        **_example("Group of the Progressive Alliance of Socialists and "
                   "Democrats in the European Parliament"),
    )


class DestinationGroup(DestinationGroupBase, table=True):
    __tablename__ = "dest_groups"
    logo_id: Optional[BlobID] = Field(
        None,
        foreign_key="blobs.id",
        description="The logo of this group.",
    )
    logo: Optional[Blob] = Relationship()
    destinations: List[Destination] = Relationship(
        back_populates="groups", link_model=DestinationGroupLink,
    )


class DestinationGroupDump(DestinationGroupBase):
    logo: Optional[str]


class DestinationGroupListItem(DestinationGroupBase):
    logo: Optional[str]


DestinationRead.update_forward_refs()


class DestinationSelectionLogPurpose(str, enum.Enum):
    # Suggested to be contacted.
    SUGGEST = "suggest"


class DestinationSelectionLogBase(SQLModel):
    """Logs every time a destination has been selected for contacting."""
    id: Optional[int] = Field(
        primary_key=True,
        description="Auto-generated ID of this selection log.",
    )
    destination_id: DestinationID = Field(
        index=True,
        foreign_key="destinations.id",
        description="ID of the destination that has been selected.",
    )
    timestamp: Optional[datetime] = Field(
        index=True,
        sa_column=auto_timestamp_column(),
        description="Timestamp of when the selection took place.",
    )
    purpose: DestinationSelectionLogPurpose = Field(
        index=True,
        sa_column=Column(Enum(DestinationSelectionLogPurpose)),
        description="The purpose of the selection.",
    )


class DestinationSelectionLog(DestinationSelectionLogBase, table=True):
    __tablename__ = "dest_select_log"
    destination: Destination = Relationship()


class SwayabilityImport(BaseModel):
    id: DestinationID = Field(
        description="ID of the Destination to manipulate.",
    )
    endorsement: Optional[Score] = Field(
        None,
        description="Base Endorsement value to set.",
    )


DumpableModels = Union[DestinationDump, DestinationGroupDump]

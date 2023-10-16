from datetime import datetime
import enum
from typing import Any, Dict, List, Optional, TypedDict, Union
from uuid import uuid4

from pydantic import UUID4, BaseModel
from sqlmodel import Column, Enum, Field, JSON, Relationship, SQLModel, \
    String, TIMESTAMP, UniqueConstraint, and_, case, or_, func, text

from ..config import Config, ConfigNotLoaded, Language
from ..models import CountryCode, FeedbackConvinced, FeedbackText, \
    FeedbackToken, MediaListItem, Score, UserPhone, VerificationCode


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


def auto_timestamp_column_kwargs() -> Dict[str, Any]:
    return {
        "nullable": False,
        "server_default": func.now(),
    }


def auto_timestamp_column(**kwargs) -> Column:
    """A timestamp column that will default to whenever the row is created.

    Note that this returns a `Column`, which will cause the field to be
    prioritized higher than normal SQLModel fields in table creation. It will
    probably be come right after the primary key. Worse yet, if it is part of
    the primary key, it will be ordered before any non-`Column` fields. If this
    breaks your ordering, use `sa_column_kwargs=auto_timestamp_column_kwargs()`
    instead. See <https://github.com/tiangolo/sqlmodel/issues/542> for details.
    """
    return Column(
        TIMESTAMP(timezone=True),
        **auto_timestamp_column_kwargs(),
        **kwargs,
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


class Call(SQLModel, table=True):
    """A Call that is currently ongoing in our System """
    __tablename__ = "calls"
    __table_args__ = (
        UniqueConstraint("provider", "provider_call_id", name="unique_call"),
    )
    id: UUID4 = Field(
        primary_key=True,
        default_factory=uuid4,
        description="A unique string to identify this Call.",
        **_example("80d35849-2527-4672-b227-0540e6133e09"),
    )
    provider: str = Field(
        description="The Provider who makes the call for us.",
        **_example("46elks"),
    )
    provider_call_id: str = Field(
        description="The Provider's Call ID.",
        **_example("c4644bcfb44e712345c36e189faba04bd"),
        index=True,
    )
    started_at: datetime = Field(
        description="Timestamp of when the call was started.",
        **_example("2021-01-01 00:00:00"),
    )
    connected_at: Optional[datetime] = Field(
        None,
        description="Timestamp of when the call was connected.",
        **_example("2021-01-01 00:00:00"),
    )
    ended_at: Optional[datetime] = Field(
        None,
        description="Timestamp of when the call was ended.",
        **_example("2021-01-01 00:00:00"),
    )
    user_language: Language = Field(
        description="The user's language.",
        **_example("en"),
    )
    user_id: UserPhone = Field(
        index=True,
        description="ID [PhoneNumber] to reuse for this call",
    )
    destination_id: DestinationID = Field(
        index=True,
        foreign_key="destinations.id",
        description="The Destination this Call belongs to.",
    )
    destination: "Destination" = Relationship()


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
    name_audio: Optional[str]


class DestinationRead(DestinationBase):
    contacts: List[ContactListItem] = []
    groups: List["DestinationGroupListItem"] = []
    portrait: Optional[str] = Field(
        description="URL path to the portrait image of this Destination, if "
        "any is available.",
        **_example("/api/v1/blob/j.m.mierscheid.jpg"),
    )


class ContactRead(ContactBase):
    destination_id: DestinationID
    destination: DestinationRead


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


DestinationRead.update_forward_refs()  # after DestinationGroupListItem


class NumberVerificationRequest(SQLModel, table=True):
    __tablename__ = "number_verification_requests"
    id: Optional[int] = Field(
        primary_key=True,
        description="Auto-generated ID.",
    )
    user: UserPhone = Field(
        index=True,
        description="User requesting the verification.",
    )
    code: VerificationCode = Field(
        description="Verification code sent out via SMS.",
    )
    # Not an auto_timestamp_column because it relates to expires_at, the caller
    # should calculate both and set them explicitly.
    requested_at: datetime = Field(
        index=True,
        description="Timestamp of when the User requested the code.",
    )
    expires_at: datetime = Field(
        description="Timestamp of when the code will expire.",
    )
    completed_at: Optional[datetime] = Field(
        index=True,
        description="Timestamp of when the request has been completed "
        "successfully (if at all) by entering the correct code.",
    )
    language: Language = Field(
        description="UI language in use when the code was requested.",
    )
    failed_attempts: int = Field(
        0,
        sa_column_kwargs={
            "server_default": text("0"),
        },
        description="Number of failed verification attempts (i.e. wrong code) "
        "while this was the most recent entry.",
    )
    ignore: bool = Field(
        False,
        description="Whether to ignore this entry, e.g. from counting the "
        "number of verification requests. To be set manually by the "
        "administrator."
    )


class DestinationSelectionLogEvent(str, enum.Enum):
    """
    Destinations may be "selected" for different reasons, and depending on the
    reason, it might have different effects on whether the Destination can be
    selected again, and if so, with which probability. The following kinds of
    selection are currently supported:

    * `WEB_SUGGESTED`: The Destination has been displayed to a User in the Web
      frontend, e.g. because the user hit “suggest random”, or searched for a
      Destination by name. This should only have a weak influence on the
      Destination’s “suggestability”: It may happen that the User decides to
      call this Destination, but they could also let the system suggest someone
      else, or not make a call at all.
    * `IVR_SUGGESTED`: The Destination has been suggested to a User who is
      currently in a call with our IVR menu. This can happen if the Destination
      the user initially requested to call is unavailable, in which case the
      system tries to suggest someone else. As the User is already on the phone
      with us, chances are relatively high that they’ll accept this suggestion
      and call that Destination.
    * `CALLING_USER`: The User has requested to be called, in order to be
      connected to this Destination. This is the case when the User clicks on
      “call now” in the web frontend. Now, the system tries to call the User’s
      phone and place them into the IVR menu, targeting this Destination.
    * `IN_MENU`: We have successfully established a call with the User, they
      are currently in the IVR menu, targeting this Destination.
    * `CALLING_DESTINATION`: The User has asked the IVR menu to be connected to
      this Destination now, all sanity checks have been completed successfully
      and the system is now trying to establish a call with the Destination.
      This means that it makes little sense to try calling the same Destination
      for another User right now.
    * `DESTINATION_CONNECTED`: The system has successfully connected the User
      and the Destination, and they are probably talking at the moment. It is
      useless to try calling this Destination for another User.
    * `FINISHED_SHORT_CALL`: The call between User and Destination has been
      completed. They were only talking for a short time, and it’s probably
      okay to assume that only an assistant or voicemail has been reached, but
      not the actual Member of Parliament.
    * `FINISHED_CALL`: The call between User and Destination has been
      completed. Also, they were talking long enough to assume that the Member
      of Parliament has actually been reached and talked to.
    * `CALL_ABORTED`: The call has been aborted prematurely, e.g. because the
      User hung up before being connected to the Destination, or because the
      User was never called due to policy reasons, etc.
    * `CALLING_USER_FAILED`: The system was unable to call the User due to an
      unexpected error. No call was established.
    * `CALLING_DESTINATION_FAILED`: The system was in a call with the User, and
      the User requested to be connected to the Destination, but the
      Destination call could not be established due to an unexpected error.
    """
    WEB_SUGGESTED = "WEB_SUGGESTED"
    IVR_SUGGESTED = "IVR_SUGGESTED"
    CALLING_USER = "CALLING_USER"
    IN_MENU = "IN_MENU"
    CALLING_DESTINATION = "CALLING_DESTINATION"
    DESTINATION_CONNECTED = "DESTINATION_CONNECTED"
    FINISHED_SHORT_CALL = "FINISHED_SHORT_CALL"
    FINISHED_CALL = "FINISHED_CALL"
    CALL_ABORTED = "CALL_ABORTED"
    CALLING_USER_FAILED = "CALLING_USER_FAILED"
    CALLING_DESTINATION_FAILED = "CALLING_DESTINATION_FAILED"


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
    user_id: Optional[UserPhone] = Field(
        index=True,
        description="ID (i.e. hashed phone number) of User that relates to "
        "this log, if any.",
    )
    call_id: Optional[str] = Field(
        index=True,
        description="ID of the phone call that relates to this log, if any.",
    )
    timestamp: Optional[datetime] = Field(
        sa_column=auto_timestamp_column(index=True),
        description="Timestamp of when the selection took place.",
    )
    event: DestinationSelectionLogEvent = Field(
        index=True,
        sa_column=Column(Enum(DestinationSelectionLogEvent)),
        description="The event type being logged, to separate the different "
        "reasons why a Destination can be selected (or de-selected for that "
        "matter).",
    )


class DestinationSelectionLog(DestinationSelectionLogBase, table=True):
    __tablename__ = "dest_select_log"
    destination: Destination = Relationship()


class UserFeedback(SQLModel, table=True):
    __tablename__ = "user_feedback"
    token: FeedbackToken = Field(
        primary_key=True,
        description="The unique token associated with this feedback entry.",
    )
    # Not an auto_timestamp_column because it relates to expires_at, the caller
    # should calculate both and set them explicitly.
    issued_at: datetime = Field(
        index=True,
        description="When the token has been issued.",
    )
    expires_at: datetime = Field(
        index=True,
        description="When the token will expire.",
    )
    feedback_entered_at: Optional[datetime] = Field(
        index=True,
        description="When the feedback has been given. Can be null if the "
        "token has not yet been used.",
    )
    destination_id: DestinationID = Field(
        index=True, foreign_key="destinations.id",
        description="The Destination this feedback is about.",
    )
    destination: Destination = Relationship()
    calling_code: int = Field(
        index=True,
        description="Calling code of the User’s country.",
    )
    language: str = Field(
        index=True,
        description="The language the User has had selected when starting the "
        "call.",
    )
    convinced: Optional[FeedbackConvinced] = Field(
        index=True,
        description="Whether the User thinks they’ve convinced the "
        "Destination.",
    )
    technical_problems: Optional[bool] = Field(
        index=True,
        description="Whether there were technical problems in the call.",
    )
    additional: Optional[FeedbackText] = Field(
        description="Additional feedback text.",
    )


class FeedbackContext(BaseModel):
    expired: bool = Field(
        description="Whether the token has already expired. This can also be "
        "true for used tokens, if they already received feedback but are now "
        "beyond their expiry date.",
        **_example(False),
    )
    used: bool = Field(
        description="Whether the token has been used for sending feedback "
        "already. This can also be true for expired tokens, if they already "
        "received feedback before expiring.",
        **_example(False),
    )
    language: Language = Field(
        description="The language the User has had selected when starting the "
        "call. Allows the frontend to initialize itself to that language, "
        "even if the User is using a completely new browser to access the "
        "feedback form.",
    )
    destination: Optional[DestinationRead] = Field(
        description="The Destination associated with this token. Will only be "
        "returned if the token is neither expired nor already used.",
    )


class SwayabilityImport(BaseModel):
    id: DestinationID = Field(
        description="ID of the Destination to manipulate.",
    )
    endorsement: Optional[Score] = Field(
        None,
        description="Base Endorsement value to set.",
    )


class MediaList(SQLModel, table=True):
    __tablename__ = "medialists"
    id: UUID4 = Field(
        sa_column=Column(
            String, primary_key=True, default=lambda: str(uuid4())),
        description="ID of the media list.",
    )
    created_at: datetime = Field(
        sa_column=auto_timestamp_column(index=True),
    )
    items: List[MediaListItem] = Field(
        sa_column=Column(JSON),
    )
    format: str = Field(
        description="The format of the desired output, compatible to ffmpeg's "
        "`-f` option, e.g. `ogg`.",
    )
    mimetype: str = Field(
        description="The MIME type the output is going to have.",
    )


DumpableModels = Union[DestinationDump, DestinationGroupDump]

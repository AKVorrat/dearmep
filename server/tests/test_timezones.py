# SPDX-FileCopyrightText: © 2025 Tim Weber
#
# SPDX-License-Identifier: AGPL-3.0-or-later

from datetime import datetime, timezone

import pytest
import pytz
from sqlalchemy.exc import StatementError
from sqlmodel import Session, select, text

from dearmep.database.models import Blob


def test_timestamps_in_db(
    session: Session, fastapi_app, with_example_destinations
):
    # Creating a blob with an automatic timestamp should just work.
    blob = Blob(type="test", mime_type="text/plain", name="test", data=b"test")
    session.add(blob)
    session.commit()
    # The timestamp should now be populated.
    assert blob.modified_at is not None
    # The timestamp should be in UTC.
    assert blob.modified_at.tzinfo == timezone.utc
    # The timestamp should be pretty close to "now".
    assert (
        abs((blob.modified_at - datetime.now(tz=timezone.utc)).total_seconds())
        < 10  # noqa: PLR2004
    )

    # Let's try creating a blob with a given, naive timestamp. Should fail.
    blob = Blob(
        type="test",
        mime_type="text/plain",
        name="test-naive",
        data=b"test",
        modified_at=datetime.now(tz=None),  # noqa: DTZ005
    )
    session.add(blob)
    with pytest.raises(StatementError, match="naive datetime"):
        session.commit()
    session.rollback()

    # Create the blob with a given aware timestamp.
    modified = pytz.timezone("America/Belize").localize(
        datetime(2025, 9, 18, 16, 0, 23)  # noqa: DTZ001
    )
    blob = Blob(
        type="test",
        mime_type="text/plain",
        name="test-aware",
        data=b"test",
        modified_at=modified,
    )
    session.add(blob)
    session.commit()
    # Retrieve the blob again.
    blob = session.exec(select(Blob).where(Blob.name == "test-aware")).one()
    # Ensure that its timestamp matches what we expect.
    assert blob.modified_at == modified
    assert (
        blob.modified_at
        - datetime(2025, 9, 18, 22, 0, 23, tzinfo=timezone.utc)
    ).total_seconds() == 0
    # Finally, check what's in the database.
    assert (
        session.execute(
            text("select modified_at from blobs where name = 'test-aware'")
        )
        .one()
        .modified_at.startswith("2025-09-18 22:00:23")
    )

from pathlib import Path
from typing import Iterable, Literal, Optional

from ...http_client import MassDownloader
from ...progress import BaseTask


PORTRAIT_URL = "https://www.europarl.europa.eu/mepphoto/{mep_id}.jpg"
NAME_AUDIO_URL = "https://www.europarl.europa.eu/mepaudio/{mep_id}.mp3"

NotFoundReaction = Literal["ignore", "save", "stop"]

IGNORE = "ignore"
SAVE = "save"
STOP = "stop"


def download_media(
    mep_ids: Iterable[int],
    *,
    url_pattern: str,
    filename_pattern: str,
    jobs: int,
    overwrite: bool = False,
    skip_existing: bool = False,
    not_found: NotFoundReaction = "stop",
    task: Optional[BaseTask] = None,
):
    downloader = MassDownloader(
        jobs=jobs,
        overwrite=overwrite,
        skip_existing=skip_existing,
        task=task,
        accept_error_codes={404} if not_found == SAVE else None,
        ignore_error_codes={404} if not_found == IGNORE else None,
    )
    downloader.start()
    for mep_id in mep_ids:
        url = url_pattern.format(mep_id=mep_id)
        filename = Path(filename_pattern.format(id=mep_id, mep_id=mep_id))
        downloader.add(url, filename)
    downloader.stop()


def download_portraits(
    mep_ids: Iterable[int],
    *,
    filename_pattern: str,
    jobs: int,
    overwrite: bool = False,
    skip_existing: bool = False,
    not_found: NotFoundReaction = "stop",
    task: Optional[BaseTask] = None,
):
    return download_media(
        mep_ids,
        url_pattern=PORTRAIT_URL,
        filename_pattern=filename_pattern,
        jobs=jobs,
        overwrite=overwrite,
        skip_existing=skip_existing,
        not_found=not_found,
        task=task,
    )


def download_name_audio(
    mep_ids: Iterable[int],
    *,
    filename_pattern: str,
    jobs: int,
    overwrite: bool = False,
    skip_existing: bool = False,
    not_found: NotFoundReaction = "stop",
    task: Optional[BaseTask] = None,
):
    return download_media(
        mep_ids,
        url_pattern=NAME_AUDIO_URL,
        filename_pattern=filename_pattern,
        jobs=jobs,
        overwrite=overwrite,
        skip_existing=skip_existing,
        not_found=not_found,
        task=task,
    )

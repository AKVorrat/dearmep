import enum


class ActionIfExists(str, enum.Enum):
    SKIP = "skip"
    OVERWRITE = "overwrite"
    FAIL = "fail"

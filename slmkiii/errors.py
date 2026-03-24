from __future__ import annotations


class ErrorFileExists(Exception):
    def __init__(self, filename: str | None = None):
        self.filename = filename
        super().__init__(f"File already exists: {filename}")


class ErrorInvalidChecksum(Exception):
    def __init__(self):
        super().__init__("SysEx template checksum does not match data")


class ErrorTooManyItemsInSection(Exception):
    def __init__(self, section: str, found: int, max_allowed: int):
        self.section = section
        self.found = found
        self.max_allowed = max_allowed
        super().__init__(
            f"Section '{section}' has {found} items, maximum allowed is {max_allowed}"
        )


class ErrorUnknownData(Exception):
    def __init__(self, data_type: type | None = None,
                 data_length: int | None = None):
        self.data_type = data_type
        self.data_length = data_length
        if data_type is not None:
            super().__init__(
                f"Unknown data: type={data_type.__name__}, length={data_length}"
            )
        else:
            super().__init__("Unknown or unrecognized template data")


class ErrorUnknownExtension(Exception):
    def __init__(self, extension: str | None = None):
        self.extension = extension
        super().__init__(f"Unknown file extension: {extension}")


class ErrorMidiDeviceNotFound(Exception):
    def __init__(self, message: str | None = None):
        if message is None:
            message = "No Novation SL MkIII MIDI ports detected"
        super().__init__(message)


class ErrorUnknownVersion(Exception):
    def __init__(self, found: float | None = None,
                 expected: float | None = None):
        self.found = found
        self.expected = expected
        if expected is not None:
            super().__init__(
                f"Unknown template version: found {found}, expected {expected}"
            )
        else:
            super().__init__(f"Unknown template version: {found}")

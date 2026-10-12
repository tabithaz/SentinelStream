import os


SERVICE_NAME = "sentinelstream"
SERVICE_VERSION = "1.4.0"
UNKNOWN_REVISION = "unknown"
MAX_METADATA_LENGTH = 128


def _bounded_metadata(name: str, default: str) -> str:
    """Return stable, printable deployment metadata suitable for metric labels."""
    value = os.getenv(name, "").strip()
    if not value or any(ord(character) < 32 for character in value):
        return default
    return value[:MAX_METADATA_LENGTH]


def runtime_provenance() -> dict[str, str]:
    return {
        "service": SERVICE_NAME,
        "version": _bounded_metadata("SENTINELSTREAM_RELEASE", SERVICE_VERSION),
        "revision": _bounded_metadata(
            "SENTINELSTREAM_REVISION",
            UNKNOWN_REVISION,
        ),
    }

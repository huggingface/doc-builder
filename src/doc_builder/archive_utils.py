import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath


def _has_unsafe_path_parts(filename: str) -> bool:
    posix_path = PurePosixPath(filename)
    windows_path = PureWindowsPath(filename)
    return (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or ".." in posix_path.parts
        or ".." in windows_path.parts
    )


def _safe_zip_members(zip_ref: zipfile.ZipFile, destination: str | Path):
    destination_path = Path(destination).resolve()
    for member in zip_ref.infolist():
        if _has_unsafe_path_parts(member.filename):
            raise ValueError(f"Unsafe ZIP member path: {member.filename}")

        target_path = (destination_path / member.filename).resolve()
        if target_path != destination_path and destination_path not in target_path.parents:
            raise ValueError(f"Unsafe ZIP member path: {member.filename}")

        yield member


def safe_extract_zip(zip_ref: zipfile.ZipFile, destination: str | Path) -> None:
    zip_ref.extractall(destination, members=_safe_zip_members(zip_ref, destination))

"""Restore a saved review snapshot using a separately supplied local media file."""
import argparse
import re
import shutil
from pathlib import Path

from . import config
from .pipeline.common import read_json, write_json
from .schema import Project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--media", type=Path, required=True)
    args = parser.parse_args()
    media = args.media.resolve(strict=True)
    if not media.is_file():
        parser.error("Media must be a file.")
    data = read_json(args.snapshot / "project.json")
    pid = data["video_id"]
    if not re.fullmatch(r"[\w-]{1,80}", pid):
        parser.error("Invalid project id.")
    destination = config.PROJECTS_DIR / f"{pid}.json"
    if destination.exists():
        parser.error(f"Refusing to overwrite existing review: {destination}")
    cache = config.CACHE_DIR / pid
    data.update(source_video=str(media), media=str(media),
                peaks=str(cache / "peaks.json"),
                audio_analysis=str(cache / "vocals_16k.wav"),
                audio_export=str(cache / "full_48k.wav"))
    Project.model_validate(data)
    peaks = args.snapshot / "peaks.json"
    read_json(peaks)
    config.ensure_dirs()
    cache.mkdir(parents=True, exist_ok=True)
    shutil.copy2(peaks, cache / "peaks.json")
    write_json(destination, data, indent=2)
    print("Restored:", destination)
    print("Audio exports require the original analysis/export WAV files separately.")


if __name__ == "__main__":
    main()

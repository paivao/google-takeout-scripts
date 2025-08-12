#!/usr/bin/env python3
"""This script is made to add metadata to exported Google Photos media.

When you make a Google Backup via "takeout.google.com", including Google Photos,
some media may not contain all metadata. Google also export a Json to every album and media
contaning their metadata. This include description, number of views, G Photos url,
geo data, people detected in photo, etc.

An album metadata is named "metadata.json", located inside de folder containing album photos.
A media metadata is named "MEDIA_NAME_WITHOUT_EXTENSION.supplemental-metadata.json". But, if the
media filename is long, the metadata filename is cropped (most filesystems support only 255 chars).

The function of this script is to use ExifTool (the best tool to deal with different types of metadata,
from multiple file types) to include "MEDIA.supplemental-metadata.json" data into media. The objective is
to maintain metadata from migrating from one cloud to another, or to maintain file in an personal backup media
without holding tons of JSON files.

[!] Currently, this script supports the photo taken time, media creation time, description and geo data.

This script can also moves metadata from original folder to another. Just in case you want to bulk inport photos without
the JSON, or to exclude them easily.
"""
import os
import pathlib
import json
import argparse
import shutil
from datetime import datetime, timezone
import unicodedata
import subprocess
from concurrent import futures

LATITUDE_REF = ('N', 'S')
LONGITUDE_REF = ('E', 'W')
EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.heic', '.heif', '.mp4', '.mov']
DATETIME_STR_FORMAT = "%Y:%m:%d %H:%M:%S"


class GPSData:
    __slots__ = ['latitude', 'longitude', 'altitude']

    def __init__(self, geoData: dict[str, float]):
        self.latitude: float = geoData.get('latitude', 0.0)
        self.longitude: float = geoData.get('longitude', 0.0)
        self.altitude: float = geoData.get('altitude', 0.0)

    def to_params(self) -> list[str]:
        if self.latitude == 0.0 and self.longitude == 0.0:
            return []
        params = [
            f"-GPSLatitude={abs(self.latitude)}",
            f"-GPSLatitudeRef={'N' if self.latitude >= 0.0 else 'S'}",
            f"-GPSLongitude={abs(self.longitude)}",
            f"-GPSLongitudeRef={'E' if self.longitude >= 0 else 'W'}"
        ]
        if self.altitude != 0.0:
            params += [
                f"-GPSAltitude={abs(self.altitude)}",
                f"-GPSAltitude={abs(self.altitude)}"
            ]
        return params


class MediaDates:
    __slots__ = ['taken_time', 'creation_time']

    def __init__(self, taken_time: dict[str, str], creation_time: dict[str, str]):
        self.taken_time = datetime.fromtimestamp(float(taken_time.get('timestamp', 0.0)), timezone.utc)
        self.creation_time = datetime.fromtimestamp(float(creation_time.get('timestamp', 0.0)), timezone.utc)
    
    def to_params(self) -> list[str]:
        taken_time = self.taken_time.strftime(DATETIME_STR_FORMAT)
        creation_time = self.creation_time.strftime(DATETIME_STR_FORMAT)
        return [
            f"-DateTimeOriginal={taken_time}",
            f"-CreateDate={creation_time}",
            f"-ModifyDate={creation_time}"
        ]


def normalize_ascii(texto):
    """Only ASCII characteres are accepted as EXIF description.
    This function uses normalization technique to remove/convert non-ASCII characters."""
    normalized_text = unicodedata.normalize('NFKD', texto)
    return ''.join(
        char for char in normalized_text if unicodedata.category(char) != 'Mn'
    )

def add_media_metadata(exiftool_exe: str, media_path: str, metadata: dict):
    """Core of the script, adds metadata to file."""
    title = metadata['title']
    cmd = [exiftool_exe, "-overwrite_original"]
    dates = MediaDates(metadata.get('photoTakenTime', {}), metadata.get('creationTime', {}))
    description = metadata.get('description')
    geo = GPSData(metadata.get('geoData', {}))
    if description:
        cmd.append(f"-Description={normalize_ascii(description)}")
    cmd += dates.to_params()
    cmd += geo.to_params()
    cmd.append(media_path)
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        return result.stderr.decode()
    return ""


def prepare_process(base_dir: pathlib.Path, metadata_dir: pathlib.Path):
    def process_json_file(exiftool_exe: str, json_path: pathlib.Path) -> str:
        with json_path.open(encoding="utf-8") as handle:
            metadata: dict = json.load(handle)
        title: str = metadata.get('title', '')
        json_dir = json_path.parent
        if not title or title == json_dir.name:
            return
        media_file = json_dir / title
        # If media file has no extension (some old media has that issue)
        if not media_file.suffix:
            # Try all common extension
            for extension in EXTENSIONS:
                tmp_media = media_file.with_suffix(extension)
                if tmp_media.is_file():
                    media_file = tmp_media
                    break
            else:
                return f'None extension media file found for "{media_file}".'
        # If media in title has extension, but file not found...
        elif not media_file.is_file():
            return f'Media file "{media_file}" not found.'
        add_media_metadata(exiftool_exe, str(media_file), metadata)
        # Move metadata file to folder
        if metadata_dir:
            new_metadata_path = metadata_dir / json_path.relative_to(base_dir)
            os.makedirs(new_metadata_path.parent, exist_ok=True)
            shutil.move(json_path, new_metadata_path)
    return process_json_file


def main():
    parser = argparse.ArgumentParser(description="Adds metadata to Google Photos media files from JSOM metadata." +
    "If you use '-m' parametar, it also moves JSON files to another folder.")
    parser.add_argument("directory", help="Directory to parse Google Photos metadata")
    parser.add_argument("-e", "--exiftool", default="exiftool", help="Exiftool executable path")
    parser.add_argument("-m", "--metadata", help="Directory to move metadata files, once they are processed")
    args = parser.parse_args()
    base_dir = pathlib.Path(args.directory)
    metadata_folder = pathlib.Path(args.metadata)
    exiftool_exe = args.exiftool
    if not os.path.isdir(base_dir):
        print(f"Error! {base_dir} is not a directory!")
        exit(1)
    if metadata_folder:
        if not os.path.isdir(metadata_folder):
            print(f"Error! {metadata_folder} is not a directory!")
            exit(1)
    json_files = list(pathlib.Path(base_dir).glob("**/*.json"))
    last_percent = 0
    print("[*] 0% complete...")
    with futures.ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        executions = [executor.submit(prepare_process(base_dir, metadata_folder), exiftool_exe, json_path) for json_path in json_files]
        for i, execution in enumerate(futures.as_completed(executions)):
            try:
                result = execution.result()
            except Exception as e:
                print(f"[!] {e}")
            if result:
                print(f"[!] Error: {result}")
            percent = i * 10000 // len(json_files)
            if percent > last_percent:
                last_percent = percent
                print(f"[*] {percent/100:.2f}% complete...")
    print("[+] Done")


if __name__ == "__main__":
    main()
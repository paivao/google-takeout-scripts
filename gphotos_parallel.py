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
import json
import argparse
import shutil
from datetime import datetime, timezone
import unicodedata
import subprocess
from concurrent import futures

LATITUDE_REF = ('N', 'S')
LONGITUDE_REF = ('E', 'W')
EXTENSIONS = ['.jpg', '.png', '.heic', '.heif', '.mp4']
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

def try_get_file(dir: str, file: str) -> str:
    """The "title" metadata field references the file name, but I noticed that,
    on old media ingested, the extension is missing. This function tries to guess based on common extension.
    Also, for some photos that are excluded, the respective metadata are still exported, so it is better
    to check if file really exists."""
    file_ext = os.path.splitext(file)[1].lower()
    if file_ext:
        file_path = os.path.join(dir, file)
        if not os.path.isfile(file_path):
            raise Exception(f'File not found: "{file_path}"')
        return file_path
    for file_ext in EXTENSIONS:
        file_path = os.path.join(dir, f"{file}.{file_ext}")
        if os.path.isfile(file_path):
            return file_path
    raise Exception(f'Could not find any extension for file: "{os.path.join(dir, file)}"')

def add_media_metadata(exiftool_exe: str, dir: str, metadata: dict):
    """Core of the script, adds metadata to file."""
    title = metadata['title']
    try:
        file_path = try_get_file(dir, title)
    except Exception as e:
        print("[!]", e)
        return
    cmd = [exiftool_exe, "-overwrite_original"]
    dates = MediaDates(metadata.get('photoTakenTime', {}), metadata.get('creationTime', {}))
    description = metadata.get('description')
    geo = GPSData(metadata.get('geoData', {}))
    if description:
        cmd.append(f"-Description={normalize_ascii(description)}")
    cmd += dates.to_params()
    cmd += geo.to_params()
    cmd.append(file_path)
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def process_json_file(exiftool_exe: str, metadata_dir: str, dir: str, json_file: str) -> str:
    metadata_fullpath = os.path.join(dir, json_file)
    with open(metadata_fullpath, encoding="utf-8") as handle:
        metadata: dict = json.load(handle)
    title = metadata.get('title')
    if title is None or title == last_dir:
            continue
        add_media_metadata(exiftool_exe, dir, metadata)
        # Move metadata file to folder
        if metadata_folder:
            new_metadata_path = os.path.join(metadata_folder, metadata_fullpath[len(base_dir)+1:])
            os.makedirs(os.path.dirname(new_metadata_path), exist_ok=True)
            shutil.move(metadata_fullpath, new_metadata_path)


def main():
    parser = argparse.ArgumentParser(description="Adds metadata to Google Photos media files from JSOM metadata." +
    "If you use '-m' parametar, it also moves JSON files to another folder.")
    parser.add_argument("directory", help="Directory to parse Google Photos metadata")
    parser.add_argument("-e", "--exiftool", default="exiftool", help="Exiftool executable path")
    parser.add_argument("-m", "--metadata", help="Directory to move metadata files, once they are processed")
    args = parser.parse_args()
    base_dir = args.directory.rstrip(os.sep)
    metadata_folder = args.metadata.rstrip(os.sep)
    exiftool_exe = args.exiftool
    if not os.path.isdir(base_dir):
        print(f"Error! {base_dir} is not a directory!")
        exit(1)
    if metadata_folder:
        if not os.path.isdir(metadata_folder):
            print(f"Error! {metadata_folder} is not a directory!")
            exit(1)
    json_files: list[tuple[str, str]] = []
    for dir, _, files in os.walk(base_dir):
        last_dir = os.path.basename(dir.rstrip(os.path.sep))
        print(f'[*] Parsing media at "{dir}"')
        for file in files:
            if not file.endswith(".json"):
                continue
            json_files.append((dir, file))
    with futures.ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        executions = [executor.submit(process_json_file, exiftool_exe, metadata_folder, dir, file) for dir, file in json_files]
        for execution in futures.as_completed(executions):
            result = execution.result()
            if result:
                print(f"[!] {result}")
        
    print("[+] Done")


if __name__ == "__main__":
    main()
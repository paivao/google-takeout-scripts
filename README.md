# Some Google Takeout Scripts

This is some scripts I made to help me with Google Takeout.

**Disclaimer:** These scripts come with no warranty, you use at your own risk!

## Google Backup

The first one, `google_backup.py`, is to check if all files exported are present.
When you use Google Takeout, it generates a bunch of _ZIP_ or _TAR.GZ_ files, but they does not
provide checksums file. Besides, the ammount of files may be enormous.

They give an navigator _HTML_ file. This script scraps this file, and check if all files are present.
It considers that all files are extracted from compressed at same folder.

You call it by:
```bash
python3 google_backup.py NAVIGATOR_HTML_FILE
```

It depends on BeautifulSoup. It is found in a lot of Linux distributions. Use them, or you can get it with `pip install beautifulsoup4`. It works on Windows too.

## Google Photos

The second script, `gphotos_parallel.py`, embeds some media metadata exported from Google Photos.

The media files exported from your Google Photos come with an metadata JSON. There are two types of them.
First one, named *metadata.json*, contains metadata about an album. And the second one is named 
*MEDIA_FILE_WITHOUT_EXTENSION.supplemental-metadata.json*, and contains metadata about an specific media file.

Since most filesystems have file size limitations, the json name may be incomplete. This scripts handle that.

This script then copy three metadata (photo datetimes, description and geo data) from the _json_ files into the respective media files.

It uses [ExifTool](https://exiftool.org/) to parse metadata from different media types. It is found in most Linux distributions, but if you use Windows, you can download it in the official website.

You call it:
```bash
python3 gphotos_parallel.py GOOGLE_PHOTOS_DIRECTORY
```

It has two optionals parameters:
- `-m METADATA_PATH` -- moves the json metadata files into this path, so you get only the media files in the original folder.
- `-e EXIFTOOL_PATH` -- you can indicate an alternative path to the ExifTool executable, instead of "exiftool". Useful on windows.

Here another example of full calling:
```bash
python3[.exe] gphotos_parallel.py -m /path/to/metadata/destination -e /path/to/exiftool "/path/to/exported/Google Photos"
```

### Not parallel google photos

The `gphotos.py` does the same thing, but it is not parallel, so it will take longer, but uses less CPU. So, your choice.
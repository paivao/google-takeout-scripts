"""This script is created to check if all files you got from an Google Backup are there.

When you export your Google data via "takeout.google.com", generally you get multiple zipped (or tar-gzipped)
files. To check if all exported files are there, Google creates an HTML file listing all exported files.

This script check this HTML file and compare with the exported files, after you extract all compressed files.

It needs beautifulsoup. You can get with: "pip install bs4".
"""
import os
import argparse
from bs4 import BeautifulSoup, Tag
from pprint import pprint

def parse_directory(tag: Tag, directory: str):
    """Check if all files described in an directory (inside navigator HTML) are there.
    It calls itself to descend all tree."""
    children = tag.children
    first_child = next(children)
    child_class = first_child['class'][0]
    # We get a folder
    if child_class == "extracted-folder":
        folder_name = first_child.find_next("div").text
        folder_name = os.path.join(directory, folder_name.strip())
        if not os.path.isdir(folder_name):
            print(f'Folder "{folder_name}" not found!')
            return
        for child in children:
            parse_directory(child, folder_name)
    elif child_class == "file-leaf":
        filename = first_child.next.text
        fullname = os.path.join(directory, filename.strip())
        if not os.path.isfile(fullname):
            print(f'"{fullname}" was not found!')
    else:
        raise Exception("unknown type")

def parse_html_file(file: BeautifulSoup, directory: str):
    """Parses navigator HTML file, service by service, to check if all files exported for each service are there."""
    services = file.find_all("div", class_="service-detail")
    for service in services:
        name = service.select_one(".service_name > h1").text
        service_path = os.path.join(directory, name)
        print(f"*** {name} ***")
        if not os.path.isdir(service_path):
            print(f"Not found!")
            continue
        rows = service.find("div", class_="extracted-list").children
        for row in rows:
            parse_directory(row, service_path)

def main():
    parser = argparse.ArgumentParser(description="Check if all backup'ed files from Google Takeout are here, once you extract all compressed files. Need to inform navigator.html.",
                                     epilog="Created by Rafael de Paula Paiva.")
    parser.add_argument("navigator_file", help="Navigator HTML file.")
    args = parser.parse_args()
    navigator_file = args.navigator_file
    if not os.path.isfile(navigator_file):
        print(f"Error! {navigator_file} not found!")
        exit(1)
    with open(navigator_file, encoding="utf-8") as handle:
        html = BeautifulSoup(handle, "html.parser")
        parse_html_file(html, os.path.dirname(navigator_file))

if __name__ == "__main__":
    main()
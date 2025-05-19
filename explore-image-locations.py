import argparse
import sqlite3
import json
from pathlib import Path
from PIL import Image
import piexif
import sys
from datetime import datetime


LOG_OUTPUT = sys.stdout


def log(message):
    # Get current date and time
    now = datetime.now()
    # Format date and time as string
    datetime_str = now.strftime("%Y-%m-%d %H:%M:%S")
    print(f'[{datetime_str}] {message}', file=LOG_OUTPUT)


def _parse_args():
    parser = argparse.ArgumentParser(prog="digikam-migration-image-location-explorer")
    parser.add_argument('images', help="Comma separated list of images to explore.",
                        nargs='?', default=None)
    parser.add_argument("--database", help="The digikam database file",
                        default='digikam4.db')
    parser.add_argument("--location-cache", help="JSON file with the location information",
                        default="locations.json")
    parser.add_argument("--apply-location", help="apply the found location to the image file",
                        action="store_true")
    parser.add_argument("--image-root", help="The root folder with the image files",
                        default="images")
    parser.add_argument("--log-file", help="File to send log of actions to, default to stdout",
                        default=None)

    return parser.parse_args()


def _print_tags(cursor, pid, indent):
    # find all tags that have the given parent ID
    cursor.execute(f"SELECT * FROM TAGS WHERE PID = {pid}")

    # Fetch all rows that match the PID value
    rows = cursor.fetchall()
    for row in rows:
        id = row[0]
        tag = row[2]
        print(f'{indent}| {tag}')
        _print_tags(cursor, id, f'{indent}--')

    return


def print_tag(tag, recursive, conn):
    # Create a cursor object to interact with the database
    cursor = conn.cursor()

    # get the ID of our tag
    cursor.execute(f'SELECT id FROM Tags Where name = "{tag}"')
    root_id = cursor.fetchone()[0]
    print(f'Tag: {tag} has the ID: {root_id}')

    if recursive:
        # recursively build our tag array
        _print_tags(cursor, root_id, '--')

    return


def check_if_gps_exists(image_path):
    # check if a file already has location headers.
    try:
        img = Image.open(image_path)
        exif_dict = piexif.load(img.info.get("exif", b""))
        gps_data = exif_dict.get("GPS", {})
        return bool(gps_data)
    except Exception as e:
        print(f"Error reading EXIF data: {e}")
        return False


def deg_to_dms_rational(deg_float):
    deg_abs = abs(deg_float)
    minutes, seconds = divmod(deg_abs * 3600, 60)
    degrees, minutes = divmod(minutes, 60)
    return [
        (int(degrees), 1),
        (int(minutes), 1),
        (int(seconds * 100), 100)
    ]


def set_gps_location(file_path, lat, lng):
    # Open image and load EXIF data
    img = Image.open(file_path)
    exif_dict = piexif.load(img.info.get('exif', b''))

    # Prepare GPS IFD
    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: 'N' if lat >= 0 else 'S',
        piexif.GPSIFD.GPSLatitude: deg_to_dms_rational(lat),
        piexif.GPSIFD.GPSLongitudeRef: 'E' if lng >= 0 else 'W',
        piexif.GPSIFD.GPSLongitude: deg_to_dms_rational(lng),
        piexif.GPSIFD.GPSVersionID: (2, 0, 0, 0),
    }
    log(f'Setting GPS location for file: {file_path}; to: {gps_ifd}')

    # Update EXIF data
    exif_dict['GPS'] = gps_ifd
    exif_bytes = piexif.dump(exif_dict)

    # Save image with new EXIF data
    img.save(file_path, "jpeg", exif=exif_bytes)


def print_image_location(image_root, location_tags, image_list, conn, apply_location):
    # Create a cursor object to interact with the database
    cursor = conn.cursor()

    # get all the images
    cursor.execute('SELECT id FROM Images')
    rows = cursor.fetchall()

    no_location_tags = []
    for row in rows:
        image = row[0]
        if len(image_list) and str(image) not in image_list:
            #print(f'image: {image} is not in the image_list')
            continue
        location = None
        cursor.execute(f'SELECT tagid FROM ImageTags Where imageid = {image}')
        tags = cursor.fetchall()
        nt = []
        for t in tags:
            tag = t[0]
            if tag in location_tags:
                location = location_tags[tag]
                continue
            else:
                nt.append(tag)
        if location is None:
            log(f'Image: {image} has no location.')
            if len(nt):
                no_location_tags = list(set(no_location_tags) | set(nt))
                #print(f'Image: {image} has no location found; has tags: {nt}')
        else:
            log(f'Image: {image} has a location:')
            log(json.dumps(location))
            cursor.execute(f'SELECT album FROM Images Where id = "{image}"')
            album_id = cursor.fetchone()[0]
            cursor.execute(f'SELECT relativePath FROM Albums Where id = "{album_id}"')
            # need to drop the leading / on the relativePath used in the database so that pathlib will
            # let us treat it as a relative path.
            relative_path = Path(cursor.fetchone()[0][1:])
            cursor.execute(f'SELECT name FROM Images Where id = "{image}"')
            filename = cursor.fetchone()[0]
            image_path = image_root / relative_path / filename
            if apply_location:
                if image_path.suffix == ".avi":
                    log(f'Not able to get/set GPS for AVI files: {image_path}')
                elif image_path.suffix == ".mov":
                    log(f'Not able to get/set GPS for MOV files: {image_path}')
                elif image_path.suffix == ".AVI":
                    log(f'Not able to get/set GPS for AVI files: {image_path}')
                elif image_path.suffix == ".ORF":
                    log(f'Not able to get/set GPS for ORF files: {image_path}')
                elif image_path.suffix == ".mp4":
                    log(f'Not able to get/set GPS for MP4 files: {image_path}')
                elif check_if_gps_exists(image_path):
                    log(f'Image already has GPS information, not applying location: {image_path}')
                else:
                    log(f'Image safe to update, applying location GPS: {image_path}')
                    set_gps_location(image_path, location['latitude'], location['longitude'])

    if len(no_location_tags):
        log(f'Image tags that have no associated location:')
        log(json.dumps(no_location_tags))


def build_location_tag_listing(location_information):
    tags = {}
    for location in location_information:
        tags[location['id']] = location

    return tags


if __name__ == "__main__":
    args = _parse_args()

    # basic logging
    if args.log_file:
        log_path = Path(args.log_file)
        if log_path.is_file():
            print(f'Log file ({log_path}) already exists, aborting.')
            exit(-1)
        LOG_OUTPUT = log_path.open("w")

    log(f'Exploring photo locations from database file: {args.database}')
    readonly_uri = 'file:' + args.database + '?mode=ro'
    log(f'-- database read-only URI: {readonly_uri}')
    connection = sqlite3.connect(readonly_uri, uri=True)

    with open(args.location_cache, 'r') as f:
        location_information = json.load(f)

    if location_information is None:
        connection.close()
        exit(-1)

    location_tags = build_location_tag_listing(location_information)

    image_list = []
    if args.images:
        image_list = args.images.split(',')
        log(f'Image list provided: {json.dumps(image_list)}')
    print_image_location(Path(args.image_root), location_tags, image_list, connection, args.apply_location)

    connection.close()

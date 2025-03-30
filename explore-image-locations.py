import argparse
import sqlite3
import json


def _parse_args():
    parser = argparse.ArgumentParser(prog="digikam-migration-image-location-explorer")
    parser.add_argument('images', help="Comma separated list of images to explore.",
                        nargs='?', default=None)
    parser.add_argument("--database", help="The digikam database file",
                        default='digikam4.db')
    parser.add_argument("--location-cache", help="JSON file with the location information",
                        default="locations.json")
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


def print_image_location(location_tags, image_list, conn):
    # Create a cursor object to interact with the database
    cursor = conn.cursor()

    # get all the images
    cursor.execute('SELECT id FROM Images')
    rows = cursor.fetchall()

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
            print(f'Image: {image} has no location found; has tags: {nt}')
        else:
            print(f'Image: {image} has a location: {location['name']}')


def build_location_tag_listing(location_information):
    tags = {}
    for location in location_information:
        tags[location['id']] = location

    return tags


if __name__ == "__main__":
    args = _parse_args()

    print(f'Exploring photo locations from database file: {args.database}')
    readonly_uri = 'file:' + args.database + '?mode=ro'
    print(f'-- database read-only URI: {readonly_uri}')
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
        print(json.dumps(image_list))
    print_image_location(location_tags, image_list, connection)

    connection.close()

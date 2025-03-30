import argparse
import sqlite3
import json


def _parse_args():
    parser = argparse.ArgumentParser(prog="digikam-migration-tag-explorer")
    parser.add_argument('tag', help="The root tag to use.", nargs='?', default=None)
    parser.add_argument("--database", help="The digikam database file",
                        default='digikam4.db')
    parser.add_argument('-r', "--recursive", help="List the tag hierarchy",
                        action="store_true")
    parser.add_argument("--location-cache", help="JSON file with the location information",
                        default="locations.json")
    parser.add_argument("--cache-locations", help="Add the tags as locations to the location cache",
                        action="store_true")

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


def _get_tag_location(cursor, pid, ancestor_tags):
    # find all tags that have the given parent ID
    cursor.execute("SELECT * FROM TAGS WHERE PID = ?", (pid,))

    # Fetch all rows that match the PID value
    rows = cursor.fetchall()
    tags = []
    for row in rows:
        id = row[0]
        tag = row[2]
        place_name = tag
        for ancestor_tag in ancestor_tags:
            place_name += ', ' + ancestor_tag
        tags.append({
            'id': id,
            'name': tag,
            'place_name': place_name,
            'latitude': None,
            'longitude': None
        })

        ancestors = [tag] + ancestor_tags
        tags.extend(_get_tag_location(cursor, id, ancestors))

    return tags


def get_tags_as_locations(tag, conn):
    # Create a cursor object to interact with the database
    cursor = conn.cursor()

    # get the ID of our tag
    cursor.execute(f'SELECT id FROM Tags Where name = "{tag}"')
    root_id = cursor.fetchone()[0]
    # recursively build our tag array
    locations = _get_tag_location(cursor, root_id, [])

    return locations


def get_toplevel_tags(conn):
    # Create a cursor object to interact with the database
    cursor = conn.cursor()

    # get the ID of root tags
    cursor.execute('SELECT name FROM Tags Where pid = 0')
    rows = cursor.fetchall()
    tags = []
    for row in rows:
        tag = row[0]
        tags.append(tag)

    return tags


if __name__ == "__main__":
    args = _parse_args()

    print(f'Exploring photo tags from database file: {args.database}')
    readonly_uri = 'file:' + args.database + '?mode=ro'
    print(f'-- database read-only URI: {readonly_uri}')
    connection = sqlite3.connect(readonly_uri, uri=True)

    if args.tag is None:
        tags = get_toplevel_tags(connection)
        for tag in tags:
            print(f'- {tag}')
    else:
        print_tag(args.tag, args.recursive, connection)
        if args.cache_locations:
            print('caching locations')
            with open(args.location_cache, 'r') as f:
                location_information = json.load(f)
            location_information.extend(get_tags_as_locations(args.tag, connection))
            with open(args.location_cache, 'w', encoding='utf-8') as f:
                json.dump(location_information, f, ensure_ascii=False, indent=4)

    connection.close()

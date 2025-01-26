import argparse
import sqlite3
from geopy.geocoders import Nominatim
import json


def _parse_args():
    parser = argparse.ArgumentParser(prog="digikam-migration-tag-explorer")
    parser.add_argument('tag', help="The root tag to use.", nargs='?', default=None)
    parser.add_argument("--database", help="The digikam database file",
                        default='digikam4.db')
    parser.add_argument('-r', "--recursive", help="List the tag hierarchy",
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

    connection.close()

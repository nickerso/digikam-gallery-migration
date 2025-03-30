import argparse
import sqlite3
from geopy.geocoders import Nominatim
import json


def _parse_args():
    parser = argparse.ArgumentParser(prog="digikam-migration")
    parser.add_argument("database", help="The digikam database file")
    parser.add_argument("--image-root", help="Path to the root of the image files.",
                        default='.')
    parser.add_argument("--cache-location-tags", help="retrieve place tags from DB and cache them",
                        action="store_true")
    parser.add_argument("--location-cache", help="JSON file with the location information",
                        default="locations.json")
    parser.add_argument("--dry-run", help="Dry run - just print out changes that would be made",
                        action="store_true")
    return parser.parse_args()


def _get_location_tags(cursor, pid, ancestor_tags):
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
            if ancestor_tag == 'North Island':
                ancestor_tag = ''
            elif ancestor_tag == 'South Island':
                ancestor_tag = ''
            place_name += ', ' + ancestor_tag
        tags.append({
            'id': id,
            'name': tag,
            'place_name': place_name,
            'latitude': None,
            'longitude': None
        })

        ancestors = [tag] + ancestor_tags
        tags.extend(_get_location_tags(cursor, id, ancestors))

    return tags


def get_location_tags(conn):
    # Create a cursor object to interact with the database
    cursor = conn.cursor()

    # get the ID of our root "Places" tag
    cursor.execute('SELECT id FROM Tags Where name = "Places"')
    places_root_id = cursor.fetchone()[0]
    print(f'Root places ID: {places_root_id}')

    # recursively build our locations array
    location_tags = _get_location_tags(cursor, places_root_id, [])

    return location_tags


class Location:
    def __init__(self, place, latitude, longitude):
        self.place = place
        self.latitude = latitude
        self.longitude = longitude

    def __repr__(self):
        return f"Location(place={self.place}, latitude={self.latitude}, longitude={self.longitude})"

    def __str__(self):
        return f"Place: {self.place}, Latitude: {self.latitude}, Longitude: {self.longitude}"


def get_location(geolocator, place_name):
    # Get the location details for the given place name
    location = geolocator.geocode(place_name)
    if location is None:
        print(f'Unable to get_location for the place: {place_name}')
        location = Location(place_name, None, None)
    return location


if __name__ == "__main__":
    args = _parse_args()

    print(f'Migrating images using the information in database file: {args.database}')
    readonly_uri = 'file:' + args.database + '?mode=ro'
    print(f'-- database read-only URI: {readonly_uri}')
    connection = sqlite3.connect(readonly_uri, uri=True)

    location_information = {}
    if args.cache_location_tags:
        location_information = get_location_tags(connection)
        with open(args.location_cache, 'w', encoding='utf-8') as f:
            json.dump(location_information, f, ensure_ascii=False, indent=4)
    else:
        with open(args.location_cache, 'r') as f:
            location_information = json.load(f)

    # need to make sure locations have location coordinates
    geolocator = None
    # want to cache locations to make sure we don't exceed limits on geocode lookup
    LOCATION_MAP = {}
    location_updated = False
    for location in location_information:
        place = location['place_name']
        if place not in LOCATION_MAP:
            if (location['latitude'] is None) or (location['longitude'] is None):
                print(f'Need to retrieve location for the place: {place}')
                if geolocator is None:
                    geolocator = Nominatim(user_agent="andres_digikam_migration_script")
                loc = get_location(geolocator, place)
                location['latitude'] = loc.latitude
                location['longitude'] = loc.longitude
                location_updated = True
            LOCATION_MAP[place] = location
        else:
            cached_location = LOCATION_MAP[place]
            if (location['latitude'] is None) or (location['longitude'] is None):
                location['latitude'] = cached_location['latitude']
                location['longitude'] = cached_location['longitude']

    if location_updated and args.cache_location_tags:
        # update the cache file
        with open(args.location_cache, 'w', encoding='utf-8') as f:
            json.dump(location_information, f, ensure_ascii=False, indent=4)

    connection.close()
    if args.dry_run:
        print("Dry Run")
    else:
        print('for real!')

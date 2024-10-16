import argparse
import sqlite3
from geopy.geocoders import Nominatim
import json


def _parse_args():
    parser = argparse.ArgumentParser(prog="digikam-migration")
    parser.add_argument("database", help="The digikam database file")
    parser.add_argument("--image-root", help="Path to the root of the image files.",
                        default='.')
    parser.add_argument("--cache-locations", help="retrieve place tags and cache locations",
                        action="store_true")
    parser.add_argument("--location-cache", help="JSON file with the location information",
                        default="locations.json")
    parser.add_argument("--dry-run", help="Dry run - just print out changes that would be made",
                        action="store_true")
    return parser.parse_args()


def get_location_tags(conn):
    # Create a cursor object to interact with the database
    cursor = conn.cursor()

    cursor.execute('SELECT id FROM Tags Where name = "Places"')
    places_root_id = cursor.fetchone()[0]
    print(f'Root places ID: {places_root_id}')

    cursor.execute("SELECT * FROM TAGS WHERE PID = ?", (places_root_id,))

    # Fetch all rows that match the PID value
    rows = cursor.fetchall()

    # Print each row that matches the PID value
    locations = []
    geolocator = Nominatim(user_agent="andres_digikam_migration_script")
    for row in rows:
        place_name = row[2]
        # Get the location details for the given place name
        location = geolocator.geocode(place_name)

        # Print the latitude and longitude
        if location:
            locations.append({
                'id': row[0],
                'name': place_name,
                'latitude': location.latitude,
                'longitude': location.longitude
            })
            print(f"Latitude: {location.latitude}, Longitude: {location.longitude}")
        else:
            print("Location not found.")

        if place_name == 'New Zealand':
            # Get the location details for the given place name
            location = geolocator.geocode(place_name + ', Auckland')
            print(f"Latitude: {location.latitude}, Longitude: {location.longitude}")
        else:
            print("Auckland not found.")


    return locations


if __name__ == "__main__":
    args = _parse_args()

    print(f'Migrating images using the information in database file: {args.database}')
    readonly_uri = 'file:' + args.database + '?mode=ro'
    print(f'-- database read-only URI: {readonly_uri}')
    connection = sqlite3.connect(readonly_uri, uri=True)
    # get the geolocation information
    location_information = {}
    if args.cache_locations:
        locations = get_location_tags(connection)
        with open(args.location_cache, 'w', encoding='utf-8') as f:
            json.dump(locations, f, ensure_ascii=False, indent=4)

    connection.close()
    if args.dry_run:
        print("Dry Run")
    else:
        print('for real!')

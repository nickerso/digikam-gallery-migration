# digikam-gallery-migration
Andre attempting to migrate some location tags done on an old computer using digikam into geotagged photos.

* `main.py` - pulls out location tags and creates a location cache JSON file, or can lookup location information to find longitude and latitude for locations.
* `explore-tags.py` - primarily to print out tag hierarchies to the console, can choose to extend the location cache with specific tags.
* `explore-image-locations.py` - seeing which images in the database have a location in the location cache.


* `locations.json` - the default location cache file
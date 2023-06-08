import analytics
import time

from math import pi, sin, cos, radians, degrees, atan2, sqrt, log, floor
from apiclient.errors import HttpError
from clients.models import Campaign
from .content import Content
from copy import deepcopy

R = 6371.0  # Radius of Earth
MAX_ZOOM = 21
WORLD = (256, 256)


def execute(endpoint):
    """
    Make a Google Analytics endpoint call. Retry 3 times if got an HttpError.
    """

    num_retries = 3
    for i in range(num_retries):
        try:
            return endpoint.execute()
        except HttpError:
            if i == num_retries - 1:
                raise
            else:
                time.sleep(1)


def get_points(campaigns, date_from, date_to):
    points = []

    # Analytics API
    service = analytics.service()

    # Account list
    accounts = execute(service.management().accounts().list())['items']

    for account in accounts:
        account_id = account['id']

        properties = execute(service.management().webproperties().list(
            accountId=account_id
        ))['items']

        for property in properties:
            property_id = property['id']

            try:
                campaign = campaigns.get(
                    google_analytics=property_id,
                )

            except Campaign.DoesNotExist:
                # Skip this campaign
                continue

            if not campaign.is_active or campaign.company.status != 'active':
                # Inactive campaign, skip it.
                continue

            # Campaign is found. Now fetching data from Core Analytics API
            profiles = execute(service.management().profiles().list(
                accountId=account_id,
                webPropertyId=property_id
            ))['items']

            for profile in profiles:
                profile_id = profile['id']

                response = execute(service.data().ga().get(
                    ids='ga:' + profile_id,
                    start_date=date_from.strftime('%Y-%m-%d'),
                    end_date=date_to.strftime('%Y-%m-%d'),
                    dimensions='ga:latitude,ga:longitude',
                    metrics='ga:visits',
                    filters='ga:country==United States',
                    max_results=5000,
                ))

                rows = response.get('rows', None)

                if not rows:
                    continue

                points.extend(rows)

                # time.sleep(2)

    # Convert to numbers
    multi_points = [(float(lat), float(lon), int(visits))
                    for lat, lon, visits in points if float(lat) != 0]

    # Resolve multiple visits to simplify clustering
    points = []
    for lat, lon, visits in multi_points:
        for _ in range(visits):
            points.append((lat, lon))

    return points


OFFSET = 268435456
RADIUS = OFFSET * pi


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Haversine distance between two points, given by lon and lat in degrees.
    """

    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)

    a = sin(d_lat / 2.0) ** 2 + \
        cos(radians(lat1)) * cos(radians(lat2)) * \
        sin(d_lon / 2.0) ** 2

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


def lon_to_x(lon):
    return round(OFFSET + RADIUS * lon * pi / 180.0)


def lat_to_y(lat):
    return round(
        OFFSET - RADIUS * log(
            (1 + sin(lat * pi / 180.0)) /
            (1 - sin(lat * pi / 180.0))
        ) / 2.0
    )


def pixel_distance(lat1, lon1, lat2, lon2, zoom):
    x1, y1 = lon_to_x(lon1), lat_to_y(lat1)
    x2, y2 = lon_to_x(lon2), lat_to_y(lat2)

    return int(sqrt((x1 - x2)**2 + (y1 - y2)**2)) >> (MAX_ZOOM - zoom)


def make_clusters(points, min_distance, zoom):
    """Cluster points."""
    # See
    # http://www.appelsiini.net/2008/introduction-to-marker-clustering-with-google-maps

    points = deepcopy(points)

    clusters = []

    while points:
        point = points.pop()
        cluster = [point]

        # Compare against all markers left.
        distances = [(target, pixel_distance(point, target, zoom))
                     for target in points]

        # Okay, if distance < min_distance, adding this to cluster.
        cluster.extend([target for target, distance in distances
                        if distance < min_distance])

        # Points left
        points = [target for target, distance in distances
                  if distance >= min_distance]

        clusters.append(cluster)

    return clusters


def cluster_center(cluster):
    """Geometric center of a cluster."""
    if not cluster:
        return

    elif len(cluster) == 1:
        return cluster[0] + (1, )

    else:
        # Several points. Okay, calculating.
        # See http://stackoverflow.com/questions/6671183/calculate-the-center-point-of-multiple-latitude-longitude-coordinate-pairs
        x, y, z = (0, 0, 0)

        for lat, lon in cluster:
            lat = radians(lat)
            lon = radians(lon)

            x += cos(lat) * cos(lon)
            y += cos(lat) * sin(lon)
            z += sin(lat)

        count = float(len(cluster))
        x = x / count
        y = y / count
        z = z / count

        lon = atan2(y, x)
        hyp = sqrt(x*x + y*y)
        lat = atan2(z, hyp)

        point = (
            degrees(lat),   # latitude,
            degrees(lon),   # longitude
            len(cluster)    # And initial points count
                            # (see this as cluster weight)
        )

        return point


def get_zoom(points, map_width, map_height):
    """Calculate optimal Google map zoom level.
    See http://stackoverflow.com/a/13274361/1245471"""

    def lat_rad(lat):
        s = sin(radians(lat))
        x2 = log((1 + s) / (1 - s)) / 2.0
        return max(min(x2, pi), -pi) / 2.0

    def zoom(map_size, world_size, fraction):
        return int(
            floor(log(map_size / float(world_size) / fraction) / log(2.0))
        )

    # Get bounds
    latitudes, longitudes = zip(*points)

    north = max(latitudes)
    south = min(latitudes)

    west = min(longitudes)
    east = max(longitudes)

    lat_fraction = (lat_rad(north) - lat_rad(south)) / pi

    lon_diff = east - west
    if lon_diff < 0:
        lon_diff += 360

    lon_fraction = lon_diff / 360.0

    lat_zoom = zoom(map_height, WORLD[1], lat_fraction)
    lon_zoom = zoom(map_width, WORLD[0], lon_fraction)

    return min(lat_zoom, lon_zoom, MAX_ZOOM)


class Map(Content):
    template = 'map.html'

    def execute(self, company, campaigns, date_from, date_to, **kwargs):
        # Total map points

        points = get_points(campaigns, date_from, date_to)

        if not points:
            return

        # Get zoom
        size = (640, 640)  # Map size on page, in pixels
        zoom = get_zoom(points, size)

        # Now clustering points.
        min_distance = 80
        clusters = make_clusters(points, min_distance, zoom)

        # So, every cluster can be reduced to its center.
        points = []
        for cluster in clusters:
            points.append(cluster_center(cluster))

        # Group by visit count
        groups = {}
        for lat, lon, label in points:
            if label < 10:
                label = 'purple'

            elif 10 <= label < 20:
                label = 'green'

            elif 20 <= label < 50:
                label = 'orange'

            else:
                label = 'red'

            if label in groups:
                groups[label].append((lat, lon))
            else:
                groups[label] = [
                    (lat, lon)
                ]

        markers = []
        for label, series in groups.items():
            markers.append('color:%s|size:small|' % label + '|'.join(
                map(
                    lambda point: '%s,%s' % (round(point[0], 4),
                                             round(point[1], 4)),
                    series
                )
            ))

        url = 'http://maps.googleapis.com/maps/api/staticmap?' + '&'\
            .join(map(lambda pair: '='.join(pair), (
                    ('maptype', 'roadmap'),
                    ('size', '%sx%s' % size),
                    ('zoom', str(zoom)),
                ) + tuple(
                    ('markers', series) for series in markers
                )
            )) + '&.png'

        return {
            'map': url
        }

    class Meta:
        abstract = True

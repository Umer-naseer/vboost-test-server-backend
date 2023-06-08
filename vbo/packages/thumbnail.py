"""Make thumbnails for package images."""

import cv2
import numpy
import operator

from os import path, makedirs
from PIL import Image, ImageDraw
from .watermark import watermark

from clients import models


WHITE = (255, ) * 4


def fit(inner, outer):
    """Fit inner rectangle into outer rectangle and return the coordinates."""

    print("Auto fit.")
    print("Inner:", inner)
    print("Outer:", outer)

    quotient = min(map(operator.__truediv__, outer, inner))

    print('Quotient:', quotient)

    scaled_inner = tuple(map(lambda size: quotient * size, inner))

    print("Scaled inner:", scaled_inner)

    half_width, half_height = tuple(size / 2.0 for size in scaled_inner)

    x, y = tuple(size / 2.0 for size in outer)
    print("Center:", (x, y))

    coordinates = [
        x - half_width,  # x1
        y - half_height,  # y1
        x + half_width,  # x2
        y + half_height,  # y2
    ]
    print('Coordinates:', coordinates)

    if coordinates[1] > 0:
        coordinates[3] -= coordinates[1]
        coordinates[1] = 0

    print('Coordinates shifted:', coordinates)

    print()

    return tuple(map(int, coordinates))


def make_thumbnails(package):
    """Build a cropped thumb for this package."""
    assert isinstance(package, models.Package)

    campaign = package.campaign

    # Find source thumbnail image
    try:
        source = package.thumbnail()
    except models.PackageImage.DoesNotExist:
        raise ValueError(
            'Package %s does not have an associated thumbnail image.' % package
        )

    if source is None:
        raise ValueError(
            'Package %s does not have an associated thumbnail image.' % package
        )

    # Get it
    try:
        image = Image.open(source.absolute_path())
    except IOError:
        raise ValueError(
            'Incoming image %s could not be found.' % source.image
        )

    # Get mask image and params
    try:
        mask = Image.open(package.campaign.type.mask.image.path)
    except IOError:
        raise ValueError('Mask image %s cannot be opened.'
                         % campaign.type.mask.image)

    # Process coordinates
    coordinates = (source.x1, source.y1, source.x2, source.y2)
    if None in coordinates:
        # Generating the coordinates automatically
        mask_size = (
            campaign.type.mask.image.width, campaign.type.mask.image.height
        )

        if None in mask_size:
            raise Exception('Invalid mask: %s' % mask)

        thumbnail = (
            source.image.width,
            source.image.height
        )
        source.image.open()

        coordinates = (source.x1, source.y1, source.x2, source.y2) \
            = fit(mask_size, thumbnail)
        source.save()

    # Prepare the logo
    try:
        logo = Image.open(package.campaign.logo.path).convert("RGBA")
    except (IOError, ValueError):
        raise ValueError('Logo image %s of campaign %s cannot be opened.'
                         % (campaign.logo, campaign))

    make_video_thumbnail(
        image, coordinates, mask, package.cropped_thumbnail_absolute_path()
    )

    # Thumbnail masked specifically for Facebook
    make_photo_thumbnail(
        image, logo, [470, 246], package.thumbnail().facebook_thumbnail_path()
    )

    # Now masked thumbnails
    for image in package.images.filter(campaign__isnull=True,
                                       is_skipped=False):
        picture = Image.open(image.absolute_path())
        picture.thumbnail((800, 800))
        make_photo_thumbnail(
            picture, logo, mask.size, image.masked_thumbnail_path()
        )


def make_video_thumbnail(image, coordinates, mask, save_to):
    # Crop image
    try:
        image = image.crop(coordinates)
    except IOError:
        raise ValueError('Incoming image %s could not be cropped. Maybe it '
                         'is corrupted?' % image)

    # Resize image to fit mask
    image = image.resize(mask.size)

    print("Resized to:", mask.size)

    # Make video thumbnail
    video_thumbnail = watermark(image, mask, (0, 0))

    # Save result
    folder = path.dirname(save_to)
    if not path.isdir(folder):
        makedirs(folder)

    video_thumbnail = video_thumbnail.convert('RGB')
    video_thumbnail.save(save_to, "JPEG", quality=95)


def get_faces_center(image):
    """Get image center in respect to faces.
    https://realpython.com/blog/python/face-recognition-with-python/
    """

    # Convert PIL image to OpenCV image
    image = cv2.cvtColor(numpy.array(image), cv2.COLOR_RGB2BGR)

    # Read the image
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    for postfix in ('default', 'alt'):
        cascade_filename = path.join(
            cv2.data.haarcascades,
            'haarcascade_frontalface_{}.xml'.format(postfix)
        )
        # Create the haar cascade
        faceCascade = cv2.CascadeClassifier(cascade_filename)
        # Detect faces in the image
        faces = faceCascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30),
            flags=cv2.CASCADE_SCALE_IMAGE,
        )
        # We got faces
        if not isinstance(faces, tuple) and faces.size:
            # Get center points for each face
            points = [(x + w / 2.0, y + h / 2.0) for x, y, w, h in faces]
            points.sort(key=operator.itemgetter(1))
            return points[0]


def stamp_logo(image, logo):
    # And put logo on
    logo_area = [d / 3.0 for d in image.size]
    logo.thumbnail(tuple(map(int, logo_area)), Image.ANTIALIAS)

    # We are ready to stamp logo on image. But let's prepare background
    # first (rect with rounded corner).
    padding = 10

    # Top-left corner of the logo itself
    topleft = [int(img_dim - logo_dim - padding)
               for img_dim, logo_dim in zip(image.size, logo.size)]

    # First, draw the rounded corner. It is just a circle; center is
    # in top-left point.
    X, Y = 0, 1
    draw = ImageDraw.Draw(image)
    draw.ellipse([
        tuple(d - padding for d in topleft),
        tuple(d + padding for d in topleft)
    ], WHITE, WHITE)

    # Now - the rest of the background figure, a polygon. Together with
    # the circle it forms a rect with rounded corner.
    draw.polygon([
        (topleft[X] - padding, image.size[Y]),  # bottom left
        # top left; left edge of the circle
        (topleft[X] - padding, topleft[Y]),
        (topleft[X], topleft[Y] - padding),  # top left; top of the circle
        (image.size[X], topleft[Y] - padding),  # top right
        (image.size[X], image.size[Y]),  # bottom right
    ], WHITE, WHITE)

    # image = watermark(image, background, tuple(d - padding for d in topleft))

    # Then, stamp the logo.
    return watermark(image, logo, tuple(topleft))


def make_photo_thumbnail(image, logo, mask_size, save_to):
    """Now the logo must be scaled down. No more than 1/3 of the image."""

    print('Image size: ', image.size)

    # Our crop area will be max possible maintaining aspect ratio
    # of `mask` image.
    # It means crop area height will be equal to `image` height OR width
    # be equal to `image` width.
    # First, let's find the quotient = crop_area.width / mask.width
    X, Y = 0, 1
    quotient_x = image.size[X] / float(mask_size[X])
    quotient_y = image.size[Y] / float(mask_size[Y])

    quotient = min(quotient_x, quotient_y)

    print('Quotient: ', quotient)

    # So, crop area size is...
    crop_area = [
        int(mask_size[X] * quotient),
        int(mask_size[Y] * quotient)
    ]

    print('Crop area: ', crop_area)

    # Okay, we know the size of crop area. We now need to select where to crop.
    # There are two ways to do that.
    # First, we get the geometric center of all faces on the image.
    center = get_faces_center(image)

    if center:  # Disabling the CV stuff here
        center = list(center)

    else:  # OpenCV has not found a single face on this image.
        print("No faces found.")
        center = [
            image.size[0] / 2.0,  # Horizontal alignment of crop area: center
            crop_area[1] / 2.0  # Vertical alignment of crop area: top
        ]

        # Here we position it at top because faces are usually on top of image.
        # Even if OpenCV does not see them.
        # tuple(d / 2.0 for d in image.size) - was used before.

    print('Center: ', center)

    # Thus, crop area may be slided right-left or up-down.
    # We need to find out how.
    if quotient_x < quotient_y:  # Sliding top-down
        print("Sliding top-down")
        center[X] = image.size[X] / 2.0
        range = sorted([
            crop_area[Y] / 2.0,
            image.size[Y] - crop_area[Y] / 2.0
        ])
        print('Range: ', range)

        if center[Y] < range[0]:
            center[Y] = range[0]

        elif center[Y] > range[1]:
            center[Y] = range[1]

    else:  # Sliding left-right
        print("Sliding left-right")
        center[Y] = image.size[Y] / 2.0
        range = sorted([
            crop_area[X] / 2.0,
            image.size[X] - crop_area[X] / 2.0
        ])

        if center[X] < range[0]:
            center[X] = range[0]

        elif center[X] > range[1]:
            center[X] = range[1]

    print('Center after correction: ', center)

    # Now let's get crop rectangle!
    crop_rect = tuple(map(int, [
        center[X] - crop_area[X] / 2.0, center[Y] - crop_area[Y] / 2.0,
        center[X] + crop_area[X] / 2.0, center[Y] + crop_area[Y] / 2.0
    ]))

    # Finally crop it!
    image = image.crop(crop_rect)

    image = stamp_logo(image, logo)

    # Save photo thumbnail
    folder = path.dirname(save_to)
    if not path.isdir(folder):
        makedirs(folder)

    image = image.convert('RGB')
    image.save(save_to, "JPEG", quality=95)

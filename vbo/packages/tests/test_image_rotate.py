import os
import math
import operator

import piexif

from PIL import Image

from unittest import TestCase

from packages.helpers import rotate_jpeg


IMAGES_ROOT = os.path.join(
    os.path.dirname(__file__),
    'images',
)


def rotate_compare(raw_image_filename, sample_image_filename):
    raw_image_path = os.path.join(IMAGES_ROOT, raw_image_filename)

    raw_image = Image.open(raw_image_path)
    exif_dict = piexif.load(raw_image.info['exif'])
    exif_bytes = piexif.dump(exif_dict)
    image_copy_path = os.path.join(IMAGES_ROOT, 'copy.jpg')
    raw_image.save(image_copy_path, exif=exif_bytes)

    rotate_jpeg(image_copy_path)

    rotated_image = Image.open(image_copy_path)
    rotated_image_hash = rotated_image.histogram()

    sample_image = Image.open(os.path.join(IMAGES_ROOT, sample_image_filename))
    sample_image_hash = sample_image.histogram()

    os.remove(image_copy_path)

    return int(math.sqrt(
        reduce(
            operator.add,
            map(
                lambda a, b: (a - b) ** 2,
                rotated_image_hash, sample_image_hash
            )
        ) / len(rotated_image_hash)
    ))


class ImageRotation(TestCase):

    def test_rotate_by_minus_90(self):
        self.assertLess(rotate_compare('2.jpg', '2s.jpg'), 700)

    def test_rotate_by_90(self):
        self.assertLess(rotate_compare('3.jpg', '3s.jpg'), 700)

    def test_rotate_by_180(self):
        self.assertLess(rotate_compare('4.jpg', '4s.jpg'), 700)

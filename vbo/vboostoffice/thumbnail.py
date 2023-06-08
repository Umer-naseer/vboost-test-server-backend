import cv2
import operator
import numpy
import os.path
import logging

from sorl.thumbnail.engines import pil_engine
from sorl.thumbnail.parsers import parse_crop
from PIL import Image, ImageEnhance, ImageDraw


logger = logging.getLogger(__name__)


class VboostEngine(pil_engine.Engine):
    WHITE = (255, ) * 4

    faces_center = None

    def create(self, image, geometry, options):
        if options.get('crop') == 'faces':
            self.faces_center = self._get_faces_center(image)

        image = super(VboostEngine, self).create(image, geometry, options)

        image = self.overlay(image, geometry, options)

        return image

    def _get_faces_center(self, image):
        """Get image center in respect to faces.
        https://realpython.com/blog/python/face-recognition-with-python/
        """

        # Convert PIL image to OpenCV image
        image = cv2.cvtColor(numpy.array(image), cv2.COLOR_RGB2BGR)

        # Read the image
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        for postfix in ('default', 'alt'):
            cascade_filename = os.path.join(
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

    def _into_range(self, value, range):
        if value < range[0]:
            return range[0]

        elif value > range[1]:
            return range[1]

        else:
            return value

    def _get_faces_offset(self, image, geometry, mask_margin=0):
        x_image, y_image = image_size = self.get_image_size(image)
        x_crop, y_crop = geometry

        logger.debug('Image size: %s', image_size)
        logger.debug('Going to crop to geometry %s', geometry)

        center = self.faces_center
        if center is None:
            x_offset, y_offset = parse_crop('top', image_size, geometry)

            logger.debug('No faces found.')

            # So that mask does not influence
            y_offset -= mask_margin

            # To crop out 20%
            top_area = image_size[1] * 0.2
            logger.debug('Adding top area %s to offset %s', top_area, y_offset)
            y_offset += top_area

            bottom_black_area = y_offset + geometry[1] - image_size[1]
            if bottom_black_area > 0:
                logger.debug('Bottom black area: %s', bottom_black_area)
                y_offset -= bottom_black_area

            return x_offset, y_offset

        else:
            # We now need to generate x_offset and y_offset of the topleft crop
            # region corner.
            x_center, y_center = center

            logger.debug('Faces center: %s', center)

            if x_crop < x_image:
                # We can move crop region horizontally.
                y_offset = 0

                # Ideal x_offset
                x_offset = int(x_center - x_crop / 2.0)

                logger.debug(
                    'Sliding horizontally, ideal x_offset = %s',
                    x_offset
                )

                # Does it fit into the image?
                x_offset = self._into_range(
                    x_offset,
                    (0, int(x_image - x_crop))
                )

            elif y_crop < y_image:
                # Moving vertically.
                x_offset = 0

                # Ideal y_offset
                y_offset = int(y_center - y_crop / 2.0)

                logger.debug(
                    'Sliding vertically, ideal y_offset = %s',
                    y_offset
                )

                # Does it fit into the image?
                y_offset = self._into_range(
                    y_offset,
                    (0, int(y_image - y_crop / 2.0))
                )
            else:
                x_offset, y_offset = 0, 0

            logger.debug('y_offset before margin cut: %s', y_offset)
            y_offset -= mask_margin
            logger.debug('And after it: %s', y_offset)

            return x_offset, y_offset

    def crop(self, image, geometry, options):
        crop = options['crop']

        if crop == 'faces':
            mask_margin = int(50.0 * (geometry[1] / 331.0)) if (
                options.get('overlay_mode') == 'mask'
            ) else 0

            x_offset, y_offset = self._get_faces_offset(
                image, geometry,
                mask_margin=mask_margin
            )

            logger.debug('Cropping: %s', (x_offset, y_offset))

            return self._crop(
                image,
                geometry[0], geometry[1],
                x_offset, y_offset
            )

        else:
            return super(VboostEngine, self).crop(image, geometry, options)

    def _scale(self, image, width, height):
        # Scaling faces center for future use in crop()
        if self.faces_center:
            factor = width / float(self.get_image_size(image)[0])
            self.faces_center = tuple(v * factor for v in self.faces_center)

        return super(VboostEngine, self)._scale(image, width, height)

    def _reduce_opacity(self, im, opacity):
        """Returns an image with reduced opacity."""
        assert opacity >= 0 and opacity <= 1
        if im.mode != 'RGBA':
            im = im.convert('RGBA')
        else:
            im = im.copy()
        alpha = im.split()[3]
        alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
        im.putalpha(alpha)
        return im

    def _watermark(self, im, mark, position, opacity=1):
        """Adds a watermark to an image."""
        orig_mode = None

        if opacity < 1:
            mark = self._reduce_opacity(mark, opacity)
        if im.mode != 'RGBA':
            orig_mode = im.mode
            im = im.convert('RGBA')
        # create a transparent layer the size of the image and draw the
        # watermark in that layer.
        layer = Image.new('RGBA', im.size, (0, 0, 0, 0))
        if position == 'tile':
            for y in range(0, im.size[1], mark.size[1]):
                for x in range(0, im.size[0], mark.size[0]):
                    layer.paste(mark, (x, y))
        elif position == 'scale':
            # scale, but preserve the aspect ratio
            ratio = min(
                float(im.size[0]) / mark.size[0],
                float(im.size[1]) / mark.size[1])
            w = int(mark.size[0] * ratio)
            h = int(mark.size[1] * ratio)
            mark = mark.resize((w, h))
            layer.paste(mark, ((im.size[0] - w) / 2, (im.size[1] - h) / 2))
        else:
            layer.paste(mark, position)
        # composite the watermark with the layer
        result = Image.composite(layer, im, layer)
        if orig_mode:
            return result.convert(orig_mode)
        return result

    def _overlay_mask(self, image, overlay):
        overlay.thumbnail(image.size, Image.ANTIALIAS)
        return self._watermark(image, overlay, (0, 0))

    def _overlay_logo(self, image, overlay):
        """overlay an image with white background at the topright corner."""

        X, Y = 0, 1

        overlay_area = [d / 3.0 for d in image.size]
        overlay.thumbnail(tuple(map(int, overlay_area)), Image.ANTIALIAS)

        # We are ready to put overlay on image. But let's prepare background
        # first (rect with rounded corner).
        padding = int(overlay.size[X] / 10.0)

        # Top-left corner of the overlay itself
        topleft = [
            int(img_dim - overlay_dim - padding)
            for img_dim, overlay_dim
            in zip(image.size, overlay.size)
        ]

        # Find out if the image is transparent
        is_transparent = False
        if overlay.mode in ('RGBA', 'LA') or (
            overlay.mode == 'P' and 'transparency' in overlay.info
        ):
            alpha = overlay.convert('RGBA').split()[-1]

            for value in alpha.getdata():
                if value < 255:
                    is_transparent = True
                    break

        # If it is NOT transparent, we need to draw a background
        if not is_transparent:
            # First, draw the rounded corner. It is just a circle;
            # center is in top-left point.
            draw = ImageDraw.Draw(image)
            draw.ellipse([
                tuple(d - padding for d in topleft),
                tuple(d + padding for d in topleft)
            ], self.WHITE, self.WHITE)

            # Now - the rest of the background figure, a polygon.
            # Together with the circle it forms a rect with rounded corner.
            draw.polygon([
                (topleft[X] - padding, image.size[Y]),  # bottom left
                # top left; left edge of the circle
                (topleft[X] - padding, topleft[Y]),
                # top left; top of the circle
                (topleft[X], topleft[Y] - padding),
                (image.size[X], topleft[Y] - padding),  # top right
                (image.size[X], image.size[Y]),         # bottom right
            ], self.WHITE, self.WHITE)

        # Then, put the overlay.
        return self._watermark(image, overlay, tuple(topleft))

    def overlay(self, image, geometry, options):
        """overlay a logo on main image with white background."""

        overlay_path = options.get('overlay')

        if overlay_path:
            mode = options.get('overlay_mode')
            func = {
                'mask': self._overlay_mask,
            }.get(mode, self._overlay_logo)

            return func(image, overlay=Image.open(overlay_path))
        else:
            return image

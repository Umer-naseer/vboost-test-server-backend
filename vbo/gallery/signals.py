from PIL import Image


def mask_alpha_dimensions(sender, instance, **kwargs):
    """Get image dimensions, base frame size, and save this to database."""

    image = Image.open(instance.image.file)
    width = instance.image.width
    height = instance.image.height

    # We suppose that no part of the mask can be left out
    # (contains zero pixels).
    data = {
        'top': None,
        'bottom': None,
        'left': width,
        'right': width,
    }

    # Pixel map
    pixels = image.load()

    if len(pixels[0, 0]) < 4:
        raise Exception('The template does not contain alpha channel.')

    for y in range(height):
        for x in range(width):
            zero = (pixels[x, y][3] < 255)

            # The pixel is zero
            if zero:
                # top: y coordinate of the first zero pixel
                if data['top'] is None:
                    data['top'] = y

                # bottom: y padding of the last zero pixel
                data['bottom'] = height - y

                # left: x coordinate of the leftmost zero pixel
                if x < data['left']:
                    data['left'] = x

                # right: x padding of the rightmost zero pixel
                if x > width - data['right']:
                    data['right'] = width - x

    # bottom- and right-padding are based on rightmost and bottom-most
    # zero pixels.
    # But we would like to know nonzero pixels.
    if data['bottom'] is None:
        data['bottom'] = height
    else:
        data['bottom'] -= 1

    if data['right'] is None:
        data['right'] = width
    else:
        data['right'] -= 1

    if data['top'] is None:
        data['top'] = height

    attrs = {'alpha_{}'.format(k): v for k, v in data.items()}
    instance._meta.model.objects.filter(pk=instance.id).update(**attrs)

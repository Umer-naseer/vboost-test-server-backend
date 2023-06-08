import piexif

from PIL import Image


def rotate_jpeg(filename):
    img = Image.open(filename)
    if 'exif' in img.info:
        exif_dict = piexif.load(img.info['exif'])

        if piexif.ImageIFD.Orientation in exif_dict['0th']:
            orientation = exif_dict['0th'].pop(piexif.ImageIFD.Orientation)

            if orientation == 1:
                return False

            if orientation == 2:
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            elif orientation == 3:
                img = img.rotate(180, resample=Image.BICUBIC, expand=True)
            elif orientation == 4:
                img = img.rotate(180, resample=Image.BICUBIC, expand=True)\
                    .transpose(Image.FLIP_LEFT_RIGHT)
            elif orientation == 5:
                img = img.rotate(-90, resample=Image.BICUBIC, expand=True)\
                    .transpose(Image.FLIP_LEFT_RIGHT)
            elif orientation == 6:
                img = img.rotate(-90, resample=Image.BICUBIC, expand=True)
            elif orientation == 7:
                img = img.rotate(90, resample=Image.BICUBIC, expand=True)\
                    .transpose(Image.FLIP_LEFT_RIGHT)
            elif orientation == 8:
                img = img.rotate(90, resample=Image.BICUBIC, expand=True)
            else:
                return False

            exif_dict['0th'][piexif.ImageIFD.Orientation] = 1
            exif_bytes = piexif.dump(exif_dict)
            img.save(filename, exif=exif_bytes)
            return True

    return False


def resize_image(filename, width=1024):
    img = Image.open(filename)
    width_percent = float(width / float(img.size[0]))
    height = int(float(img.size[1]) * width_percent)
    try:
        img = img.resize((width, height), Image.ANTIALIAS)
        img.save(filename, 'JPEG')
    except IOError:
        print("cannot create thumbnail for '%s'" % filename)
    return img


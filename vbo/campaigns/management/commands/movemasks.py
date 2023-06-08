import os

from hashlib import md5

from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile

from clients.models import Campaign
from gallery.models import Mask


class Command(BaseCommand):
    help = 'Temporary command instead of buggy data migration.'

    def handle(self, *args, **options):
        masks = {}
        campaigns = Campaign.objects.filter(type__isnull=False).iterator()
        for c in campaigns:
            if c.mask_image:
                content = c.mask_image.read()
                hash = md5(content).hexdigest()
                name = os.path.basename(c.mask_image.name)
                if hash not in masks:
                    mask = Mask(
                        alpha_left=c.mask_left,
                        alpha_top=c.mask_top,
                        alpha_right=c.mask_right,
                        alpha_bottom=c.mask_bottom,
                    )
                    mask.image.save(name, ContentFile(content))
                    mask.save()
                    masks[hash] = mask
                c.type.mask = masks[hash]
                c.type.save()
        print "Done."

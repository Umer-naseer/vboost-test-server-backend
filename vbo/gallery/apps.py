from django.apps import AppConfig
from django.db.models.signals import post_save


class GalleryConfig(AppConfig):
    name = 'gallery'

    def ready(self):
        from .signals import mask_alpha_dimensions
        post_save.connect(mask_alpha_dimensions, sender='gallery.Mask')

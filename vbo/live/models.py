import os

from django.db import models
from django.conf import settings


class Link(models.Model):
    TYPE_CHOICES = [
        ('social', 'Social net'),
        ('review', 'Review site'),
        ('website', 'Website'),
    ]

    company = models.ForeignKey('clients.Company', related_name="links")
    campaign = models.ForeignKey(
        'clients.Campaign', related_name="links",
        blank=True, null=True
    )
    type = models.CharField(
        max_length=120, choices=TYPE_CHOICES,
        db_index=True
    )
    value = models.URLField(db_index=True)
    title = models.CharField(max_length=120, blank=True)
    position = models.PositiveSmallIntegerField(
        default=0, blank=False,
        null=False, db_index=True
    )
    artwork = models.ForeignKey(
        'gallery.Image', on_delete=models.SET_NULL,
        blank=True, null=True
    )

    def get_site(self):
        if 'yelp.com' in self.value:
            return 'yelp'
        elif 'google.com' in self.value:
            return 'google'
        elif 'dealerrater.com' in self.value:
            return 'dealerrater'
        elif 'edmunds.com' in self.value:
            return 'edmunds'
        else:
            return self.type

    def get_default_logo_by_value(self):
        from gallery.models import Image
        logo_name = 'default_{}_logo'.format(self.get_site())
        try:
            return Image.objects.get(name=logo_name)
        except Image.DoesNotExist:
            return None

    def save(self, *args, **kwargs):
        if self.artwork is None:
            self.artwork = self.get_default_logo_by_value()

        return super(Link, self).save(*args, **kwargs)

    def __str__(self):
        return ''  # self.type

    class Meta:
        verbose_name = "Link"
        verbose_name_plural = "Links"
        ordering = ('position',)


class MontageVideo(models.Model):
    name = models.CharField(max_length=255, unique=True)
    company = models.ForeignKey(
        'clients.Company', related_name="montage_video")
    date = models.DateField(null=True, blank=True, db_index=True)
    is_visible = models.BooleanField(default=True, db_index=True)
    image = models.ImageField(blank=True, upload_to='montage/images/')
    video = models.FileField(blank=True, upload_to='montage/videos/')

    def get_thumbnail_image(self):
        # return os.path.join(settings.MONTAGE_ROOT, 'images',
        # '%s.jpg' % self.name)
        return os.path.join(settings.MEDIA_ROOT, self.image.name)

    def is_thumbnail_image_exist(self):
        if os.path.exists(self.get_thumbnail_image()):
            return True
        else:
            return False

    def get_video_url(self):
        return os.path.join(settings.MEDIA_URL, str(self.video))

    def get_video_path(self):
        return os.path.join(
            settings.MONTAGE_ROOT, 'videos',  '%s.mp4' % self.name)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Montage Video"
        verbose_name_plural = "Montage Videos"


# @receiver(signals.post_save, sender=MontageVideo, dispatch_uid='on_new_montage_video')
# def on_new_montage_video(sender, instance, created=False, raw=False, **kwargs):
#     """On a new loaded montage video"""
#     if created:
#         make_montage_thumbnail_cv2(instance)

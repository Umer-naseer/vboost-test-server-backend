from django.db import models

# Create your models here.
from sorl.thumbnail import ImageField


class Image(models.Model):
    name = models.CharField(max_length=255, unique=True)
    image = ImageField(upload_to='gallery/images')
    company = models.ForeignKey('clients.Company', null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ('name',)


class Mask(models.Model):
    image = models.ImageField(upload_to='gallery/masks')
    alpha_left = models.IntegerField(blank=True, null=True)
    alpha_top = models.IntegerField(blank=True, null=True)
    alpha_right = models.IntegerField(blank=True, null=True)
    alpha_bottom = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return unicode(self.image)

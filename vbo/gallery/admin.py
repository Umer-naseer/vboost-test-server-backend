from django.contrib import admin
from django.utils.safestring import mark_safe

# Register your models here.
from sorl.thumbnail import get_thumbnail
from sorl.thumbnail.admin import AdminImageMixin

from gallery import models, forms
from generic.decorators import allow_tags
from generic.admin import Illustrated


@admin.register(models.Image)
class ImageAdmin(AdminImageMixin, admin.ModelAdmin):
    list_display = ('preview', 'name', 'image')
    list_filter = ('company', )

    @allow_tags
    def preview(self, obj):
        """Preview on the list of Image's entries for admin site."""

        return '<img src="{}"/>'.format(
            get_thumbnail(
                obj.image,
                '100',
                format="PNG"
            ).url
        ) if obj.image else None


@admin.register(models.Mask)
class MaskAdmin(Illustrated, AdminImageMixin, admin.ModelAdmin):
    form = forms.MaskForm
    list_display = ('preview', 'image')
    readonly_fields = ('mask', 'mask_params')
    fieldsets = (
        ('Mask', {'fields': ('mask', 'mask_params', 'image')}),
    )

    @allow_tags
    def preview(self, obj):
        """Preview on the list of Image's entries for admin site."""

        return '<img src="{}"/>'.format(
            get_thumbnail(
                obj.image,
                '100',
                format="PNG"
            ).url
        ) if obj.image else None

    def mask(self, obj):
        """Mask base area in readable form."""

        return self._image(obj.image)

    def mask_params(self, obj):
        return mark_safe(
            """<strong>Dimensions:</strong> %sx%s<br/><strong>Base Frame:</strong> Top %s, Right %s, Bottom %s, Left %s""" % (
            obj.image.width, obj.image.height,
            obj.alpha_top, obj.alpha_right,
            obj.alpha_bottom, obj.alpha_left,
        ))

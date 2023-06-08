from .models import Template
from django.contrib.admin import ModelAdmin
from django.contrib.admin import site
from django.core import urlresolvers
from django.contrib.contenttypes.models import ContentType
from generic.decorators import allow_tags, short_description


class TemplateAdmin(ModelAdmin):
    fields = ('name', 'type', 'key', 'template', 'used_by')
    search_fields = ('name', 'key', 'template')
    list_display = ('name', 'type', 'key', 'count')
    readonly_fields = ('used_by', 'count')

    list_filter = ['type']

    @allow_tags
    def used_by(self, obj):
        """List of campaigns"""

        if obj.type == 'snippet':
            return

        objects = obj.related()

        if objects is not None:
            objects = objects.all()

        if not objects:
            return 'No objects appear to use this.'

        if objects[0].__class__.__name__ == 'Campaign':
            content_type = \
                ContentType.objects.get_for_model(objects[0].__class__)
            return '<br/>'.join('<a href="%(url)s">%(name)s</a>' % {
                'url': urlresolvers.reverse(
                    "admin:%s_%s_change" % (
                        content_type.app_label,
                        content_type.model
                    ),
                    args=(instance.id,)
                ),
                'name': instance.name,
            } for instance in objects)

        else:
            return '<br/>'.join(str(instance) for instance in objects)

    @short_description('Objects using')
    def count(self, obj):
        related = obj.related()
        if related:
            return related.count()

    class Media:
        css = {
            'all': (
                'templates/templates.css',
                'templates/codemirror/lib/codemirror.css',
                'templates/codemirror/addon/hint/show-hint.css',
            )
        }
        js = (
            'templates/codemirror/lib/codemirror.js',
            'templates/codemirror/addon/hint/show-hint.js',
            'templates/codemirror/addon/hint/xml-hint.js',
            'templates/codemirror/mode/xml/xml.js',
            'templates/codemirror/mode/javascript/javascript.js',
            'templates/codemirror/mode/css/css.js',
            'templates/codemirror/mode/jinja2/jinja2.js',
            'templates/codemirror/mode/htmlmixed/htmlmixed.js',
            'templates/codemirror/addon/mode/overlay.js',
            'templates/codemirror/addon/mode/multiplex.js',
            'templates/templates.js',
        )


site.register(Template, TemplateAdmin)

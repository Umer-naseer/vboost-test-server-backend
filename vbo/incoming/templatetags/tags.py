from django import template
from django.contrib.admin.templatetags.admin_list import result_list

register = template.Library()
register.inclusion_tag(
    'admin/clients/package/change_list_results.html'
)(result_list)

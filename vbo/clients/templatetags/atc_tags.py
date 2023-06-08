from django import template
from django.contrib.admin.templatetags.admin_list import result_list, results, result_hidden_fields, result_headers
import json


def result_list(cl):
    """Alter the result list to add mask data. Bad hack."""

    rows = list(results(cl))
    for image, row in zip(cl.result_list, rows):
        campaign = image.package.campaign

        if not campaign.type.mask.image:
            row.mask = None
        else:
            row.mask = json.dumps({
                'image': campaign.type.mask.image.url,

                'width': campaign.type.mask.image.width,
                'height': campaign.type.mask.image.height,

                'top': campaign.type.mask.alpha_top,
                'right': campaign.type.mask.alpha_right,
                'bottom': campaign.type.mask.alpha_bottom,
                'left': campaign.type.mask.alpha_left,
            })

    headers = list(result_headers(cl))
    num_sorted_fields = 0
    for h in headers:
        if h['sortable'] and h['sorted']:
            num_sorted_fields += 1
    return {'cl': cl,
            'result_hidden_fields': list(result_hidden_fields(cl)),
            'result_headers': headers,
            'num_sorted_fields': num_sorted_fields,
            'results': rows}


register = template.Library()
register.inclusion_tag(
    'admin/clients/packageimage/change_list_results.html'
)(result_list)

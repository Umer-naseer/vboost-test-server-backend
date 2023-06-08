from django.shortcuts import render

from django.http import HttpResponse
from django.views import View

class UsersView(View):

    def get(self, request):
        now = datetime.now()
        html = "<div>We will handle users active and inactive functionality here</div>".format(now)
        return HttpResponse(html)

from clients.models import Campaign
from django.db import models


class BoTR(models.Model):
    """
    Number of views, page views, and total time viewed per campaign
    per date, taken from BoTR.
    See botr_import management command.
    """

    campaign = models.ForeignKey(Campaign, related_name='views')
    date = models.DateField()
    views = models.PositiveIntegerField(default=0)
    page_views = models.PositiveIntegerField(default=0)
    viewed = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('campaign', 'date')


class AddThis(models.Model):
    """Share count per campaign per service per date."""
    campaign = models.ForeignKey(Campaign, related_name='shares')
    date = models.DateField()
    service = models.CharField(max_length=64)
    count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return '%s at %s: %s - %s' % (
            self.campaign,
            self.date,
            self.service,
            self.count
        )

    class Meta:
        unique_together = ('date', 'campaign', 'service')

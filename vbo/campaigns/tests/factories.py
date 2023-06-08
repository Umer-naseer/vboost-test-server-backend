import factory


class CampaignTypeFactory(factory.DjangoModelFactory):
    name = factory.Sequence(lambda n: 'Acme Template #{}'.format(n))

    class Meta:
        model = 'campaigns.CampaignType'

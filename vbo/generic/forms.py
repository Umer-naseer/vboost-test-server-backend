from concurrency.admin import ConcurrentBaseModelFormSet


class ConcurrentFormSet(ConcurrentBaseModelFormSet):
    """
    This formset is ought for use in concurrent multi-user environments
    """

    def total_form_count(self):
        count = super(ConcurrentFormSet, self).total_form_count()

        if self.data:
            total_form_count     = int(self.data['form-TOTAL_FORMS'])
            total_instance_count = self.queryset.count()
            if total_form_count != total_instance_count:
                return total_instance_count

        return count

    def initial_form_count(self):
        count = super(ConcurrentFormSet, self).initial_form_count()

        if self.data:
            initial_form_count     = int(self.data['form-INITIAL_FORMS'])
            initial_instance_count = self.queryset.count()
            if initial_form_count != initial_instance_count:
                return initial_instance_count

        return count

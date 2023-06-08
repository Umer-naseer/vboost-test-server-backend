django.jQuery(function() {
    // Adding a contact, we should take in account the params of this report.

    var $ = django.jQuery;

    $('#id_company').change(function() {
        var company_id = $(this).val();

        $('#add_id_contacts').attr(
            'href',
            '/clients/contact/add/?is_popup=1&company=' + company_id + '&type=manager'
        );
    }).change();
});
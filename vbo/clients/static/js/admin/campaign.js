var $ = django.jQuery;

window.onload = function () {

    function sharing_description_changing() {
        $('#id_sharing_description').text(
            'From Your Friends at ' + $('#id_company option:selected').text()
        )
    }

    function default_from_changing() {
        $('#id_default_from').attr(
            'placeholder', $('#id_company option:selected').text()
        )
    }

    function default_subject_changing() {
        $('#id_default_subject').attr(
            'placeholder', 'Your Photos from '
            + $('#id_company option:selected').text()
        )
    }

    $("#id_company").change(function () {
        sharing_description_changing();
        default_from_changing();
        default_subject_changing();
    });
};

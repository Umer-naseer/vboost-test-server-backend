$ = jQuery;
$(function() {
    $('.videoplayer').click(function () {
        var href = $(this).attr('href');

        $('#videoplayer').html('<video style="width: 800px" src="' + href + '" controls />');

        new MediaElementPlayer('video', {
            videoWidth: '100%',
            videoHeight: '100%',
            enableAutosize: true
        });
        
        $.magnificPopup.open({
            items: {
                src: '#videoplayer'
            },
            type: 'inline'
        });

        return false;
    });
});
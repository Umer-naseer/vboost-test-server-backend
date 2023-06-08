function on_desktop() {
    // If photo is aligned with video
    var eps = 10,
        video = $('a > [id^=botr]'),
        photo = $('.photo');

    return (Math.abs(photo.offset().top - video.offset().top) < eps);
};

function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie != '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = jQuery.trim(cookies[i]);
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) == (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
};


function csrfSafeMethod(method) {
    // these HTTP methods do not require CSRF protection
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
};


function video_event(event_type, current_time) {
    var delta = current_time - playback.current_time;

    if ((delta > 0) && (delta < 1)) {
        // Okay, delta is eligible. Add it.
        playback.duration += delta;
    }

    console.log(event_type, playback.duration);

    playback.current_time = current_time;

    if ((event_type != 'timeupdate') || (playback.previous_duration == null) || ((playback.duration - playback.previous_duration) > 3)) {
        if ((playback.event_id) && (playback.event_id != 'waiting')) {
            $.ajax({
                method: 'PATCH',
                url: '/api/v1/events/' + playback.event_id + '/?format=json',
                data: {
                    type: 'video',
                    duration: Math.round(playback.duration)
                }
            });
        } else if (playback.event_id != 'waiting') {
            playback.event_id = 'waiting';
            $.post('/api/v1/events/?format=json', {
                package: package_id,
                type: 'video',
                duration: Math.round(playback.duration),
            }, function(response) {
                playback.event_id = response.id;
            });
        }

        playback.previous_duration = playback.duration;
    }

}

function handle_mediaelement() {
    window.player = new MediaElementPlayer('video', {
        videoWidth: '100%',
        videoHeight: '100%',
        enableAutosize: true,
        success: function(media_element, dom_object) {
            var duration = 0,
                last_duration = null,

                current_time = 0,
                previous_time = 0;

            window.event_id = null;

            fadeOutStartVolume = 0;

            function listen(event) {
                video_event(event.type, media_element.currentTime);
            }

            media_element.addEventListener('play', listen);
            media_element.addEventListener('pause', listen);
            media_element.addEventListener('ended', listen);
            media_element.addEventListener('timeupdate', listen);

            media_element.addEventListener('timeupdate', function(e) {
                if (media_element.duration && !fadeOutStartVolume) {
                    var timeLeft = media_element.duration - media_element.currentTime;
                    if (timeLeft <= 2.0) {
                        fadeOutStartVolume = media_element.volume;
                        $(media_element).animate({volume: 0.0}, timeLeft * 1000, function() {
                            media_element.volume = fadeOutStartVolume;
                            fadeOutStartVolume = 0;
                        });
                    }
                }
            });

            media_element.addEventListener('ended', function(e) {
                // Revert to the poster image when ended
                var $thisMediaElement = (media_element.id) ? jQuery('#'+media_element.id) : jQuery(media_element);
                $thisMediaElement.parents('.mejs-inner').find('.mejs-poster').show();
            });
        }
    });
}

function handle_jwplayer() {
    var player = jwplayer(),
        video = $('a > [id^=botr]'),
        photo = $('.photo');

    function adjust(height) {
        //var height = height // + (420 - 378);
        if (on_desktop()) {
            // We are on desktop.
            // Match photo height with video height
            photo.css('height', height + 'px')
                .css('width', 'auto');
        } else {
            // We are on a mobile device.
            photo.css('height', 'auto');
        }
    };

    player.onReady(function() {
        adjust(player.getHeight());
    })

    player.onResize(function(size) {
        adjust(size.height);
    });

    function listen(event) {
        var event_type;

        if (event.newstate == 'PLAYING') {
            event_type = 'play';
        } else if (event.oldstate == 'PLAYING') {
            event_type = 'pause';
        } else if (event.type == 'jwplayerMediaTime') {
            event_type = 'timeupdate';
        } else if (event.type == 'jwplayerMediaComplete') {
            event_type = 'pause';
        } else {
            event_type = event.type;
        }

        video_event(
            event_type,
            event.position ? event.position : window.current_time
        );
    }

    player.onTime(listen);
    player.onPlay(listen);
    player.onPause(listen);
    player.onComplete(listen);
    player.onIdle(listen);
}

$(function() {
    window.playback = {
        current_time: 0,
        duration: 0,
        event_id: null
    };

    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", getCookie('csrftoken'));
            }
        }
    });

    if (window.jwplayer) {
        handle_jwplayer();
    } else {
		setTimeout(handle_mediaelement, 3000);
		setTimeout(handle_mediaelement, 2000);
		setTimeout(handle_mediaelement, 1000);
        handle_mediaelement();
    }

    window.addthis.addEventListener('addthis.menu.share', function(evt) {
        var service = evt.data.service;
        $.post('/api/v1/events/?format=json', {
            package: window.package_id,
            type: 'share',
            service: service,
            description: 'Shared via ' + service + '.'
        });
    });

    $('#gallery-trigger').click(function() {
        $.magnificPopup.open({
            items: {
                src: '#photo-gallery'
            },
            type: 'inline'
        });
    });
});


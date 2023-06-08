/* Attaching Jcrop */
$('document').ready(function() {
    $('.image').click(function() {
        // The thumbnail image
        var display = this;

        // Scaled thumbnail size
        var thumb = {
            width: this.width,
            height: this.height,
        };

        // Proxy object to figure out actual image size
        var img = new Image();
        img.onload = function() {
            // Actual image size
            var actual = {
                width: this.width,
                height: this.height,
            };

            // Scale ratio
            var ratio = actual.width / thumb.width;

            // Loading the template data
            $.getJSON(
                $(display).data('frame'),
                function(data) {
                    // We draw two rectangles on the image: inner and outer. Inner rectangle is the same as selection area. The user can select it and it covers the main section of resulting masked image. Here is the minimal size of actual inner rectangle.
                    var actual_initial_inner = {
                        width: data.width - data.left - data.right,
                        height: data.height - data.top - data.bottom,
                    };

                    // Outer rectangle is generally larger than inner one. It represents the whole mask. So, it has some padding, so that to put inner rectangle properly.
                    var actual_initial_outer = data;

                    // In fact, user can make inner rectangle larger than it is initially set, but not smaller. It is a minimal size. But the source image actually could be smaller, and we must scale the inner and outer rectangles down to fit.
                    var xfraction = actual_initial_inner.width / actual.width,
                        yfraction = actual_initial_inner.height / actual.height;

                    // Both of these fractions must be <= 1.
                    var max_fraction = Math.max(xfraction, yfraction);
                    if (max_fraction > 1) {
                        // Inner rectangle
                        actual_initial_inner.width /= max_fraction;
                        actual_initial_inner.height /= max_fraction;

                        // Outer rectangle padding
                        actual_initial_outer.top /= max_fraction;
                        actual_initial_outer.left /= max_fraction;
                        actual_initial_outer.bottom /= max_fraction;
                        actual_initial_outer.right /= max_fraction;
                    }
                    
                    // Now, actual inner and outer rectangles are set correctly. But this is not the end, because on screen the actual image is scaled by `ratio` to sizes denoted in `thumb`. We must scale our rectangles as well.

                    var scaled_initial_inner = {
                        width: actual_initial_inner.width / ratio,
                        height: actual_initial_inner.height / ratio,
                    };

                    var scaled_initial_outer = {
                        top: actual_initial_outer.top / ratio,
                        left: actual_initial_outer.left / ratio,
                        bottom: actual_initial_outer.bottom / ratio,
                        right: actual_initial_outer.right / ratio,
                    }
                    
                    // Ok, now we know what to show on screen. But where to place the rectangles? It's clear that inner rectangle should be in the center of screen.
                    var initial_inner_topleft = {
                        x: thumb.width  / 2  - scaled_initial_inner.width / 2,
                        y: thumb.height / 2 - scaled_initial_inner.height / 2
                    }

                    var initial_inner = [
                        initial_inner_topleft.x, initial_inner_topleft.y, //x1, y1
                        scaled_initial_inner.width, // width
                        scaled_initial_inner.height, // height
                    ]

                    // The hidden input which stores coordinates
                    var coords = $('#' + display.id + '-coords');
                    
                    // Set Jcrop
                    $(display).Jcrop({
                        setSelect: initial_inner,
                        minSize: [scaled_initial_inner.width, scaled_initial_inner.height],
                        allowSelect: false,
                        allowResize: true,
                        aspectRatio: scaled_initial_inner.width / scaled_initial_inner.height,
                    }, function() {
                        // Attach mask
                        var template = $(display).data('template');
                        var holder = this.ui.holder[0];
                        var tracker = $(this.ui.selection[0]).find('.jcrop-tracker')[0];

                        this.setOptions({
                            onChange: function(c) {
                                // The user may have resized the inner rectangle.
                                var width  = c.x2 - c.x,
                                    height = c.y2 - c.y;

                                // What is the resize (scale) factor?
                                var scale = width / scaled_initial_inner.width;

                                // Now, we should get the scaled outer rectangle.
                                var x1 = Math.round(c.x - scaled_initial_outer.left * scale),
                                    y1 = Math.round(c.y - scaled_initial_outer.top * scale);

                                var x2 = Math.round(c.x2 + scaled_initial_outer.right * scale),
                                    y2 = Math.round(c.y2 + scaled_initial_outer.bottom * scale);

                                // Holder background image
                                holder.style.backgroundPosition = x1 + 'px ' + y1 + 'px';
                                holder.style.backgroundSize = (x2 - x1) + 'px ' + (y2 - y1) + 'px';
                                holder.style.opacity = 0.9;

                                // Tracker background image
                                tracker.style.backgroundPosition = (- scaled_initial_outer.left * scale) + 'px ' + (- scaled_initial_outer.top * scale) + 'px';
                                tracker.style.backgroundSize = holder.style.backgroundSize;

                                // Update values
                                coords.val(
                                    x1 * ratio + ',' + y1 * ratio + ','
                                    + x2 * ratio + ',' + y2 * ratio
                                );
                            },
                        });

                        if (holder.style.backgroundSize != undefined) {
                            holder.style.backgroundImage = 'url(' + template + ')';
                            holder.style.backgroundSize  = scaled_initial_outer.width + 'px';
                            holder.style.backgroundRepeat = 'no-repeat';

                            tracker.style.backgroundImage = 'url(' + template + ')';
                            tracker.style.backgroundSize = scaled_initial_outer.width + 'px';
                            tracker.style.backgroundPosition = (- scaled_initial_outer.left) + 'px ' + (- scaled_initial_outer.top) + 'px';
                        }
                    });
                }
            );
        };

        img.src = this.src;
    });
});

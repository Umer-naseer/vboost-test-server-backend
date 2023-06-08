/*var InlineOrdering = {

    /**
     * Get list of elements that can be reordered
     *
     * At this point, only already existent records can be reordered (ie. where pk != '')
     *
     * @return Array
     * @todo Check if given record changed, and if so, make it reorderable
     * @todo Primary key might not be 'id' - better selector needed
     *
     *//*
    getOrderables: function () {
        var allInlineRows = InlineOrdering.jQuery('.package-images .package-image'),
            i = 0,
            ids = [];

        for (i = 0; i < allInlineRows.length; i = i + 1) {
            if (InlineOrdering.jQuery('.inline_ordering_position input, .field-inline_ordering_position input, input[id', allInlineRows[i]).val()) {
                ids.push('#' + allInlineRows[i].id);
            }
        }
        
        // this redundant way is required, so that proper order is maintained, 
        // otherwise orderables were returned in more or less random order
        return InlineOrdering.jQuery(ids.join(', ')); 
    },*/
    
    /**
     * Inits the jQuery UI D&D
     *
     *//*
    init: function (jQuery) {
        InlineOrdering.jQuery = jQuery;

        InlineOrdering.jQuery(".package-images").sortable({
            //axis: 'y',
            //placeholder: 'ui-state-highlight',
            handle: '.package-thumbnail',
            forcePlaceholderSize: 'true',
            items: InlineOrdering.getOrderables(),
            update: InlineOrdering.update,
        });
        //jQuery(".package-images").disableSelection();
        
        InlineOrdering.jQuery('div.field-inline_ordering_position').hide();
        InlineOrdering.jQuery('div.inline_ordering_position').hide();
        InlineOrdering.jQuery('td.inline_ordering_position input').hide();
        
        InlineOrdering.jQuery('.add-row a').click(InlineOrdering.update);
        
        InlineOrdering.getOrderables().css('cursor', 'move');
        
        InlineOrdering.update();
    },
    
    jQuery: null,
    
    *//**
     * Updates the position field
     *
     *//*
    update: function () {
        InlineOrdering.getOrderables().each(function (i) {
            //InlineOrdering.jQuery('input[id$=inline_ordering_position]', this).val(i + 1);
            //InlineOrdering.jQuery(this).find('h3 > span.position').remove();
            //InlineOrdering.jQuery(this).find('h3').append('<span class="position">#' + (i + 1).toFixed() + '</span>');
        });
    }
    
};*/

var Sorter = {
    init: function() {
        $('.package-images').each(function(i, images) {
            $(images).sortable({
                items: Sorter.get_images(images),
                handle: '.package-thumbnail',
                forcePlaceholderSize: 'true',
                update: Sorter.update,
            });
        });
    },

    get_images: function(images) {
        return $('.package-image', $(images));
    },

    update: function() {
        // List of images
        Sorter.get_images(this).each(function (i) {
            $('input[id$=inline_ordering_position]', this).val(i + 1);
        });
    }
};

function set_thumbnail() {
    if (this.checked) {
        var is_thumbnail = this,
            $is_thumbnail = $(is_thumbnail);

        // If an image is a thumb, it cannot be skipped.
        var is_skipped = $('#' + is_thumbnail.id.replace('thumbnail', 'skipped'))[0];
        if (is_skipped.checked) {
            is_skipped.checked = false;
            $(is_skipped).change();
        }

        /*
        - There is only one set "thumb" flag in image set.
        */
        var $imageset = $is_thumbnail.parents('.package-images');
        $('input[type="checkbox"][id$=is_thumbnail]', $imageset).each(function(i, item) {
            if (item != is_thumbnail) {
                this.checked = false;
                $(this).change();
            }
        })
    };
}

function set_skipped() {
    if (this.checked) {
        var is_thumbnail = $('#' + this.id.replace('skipped', 'thumbnail'))[0];
        is_thumbnail.checked = false;
        $(is_thumbnail).change();
    }
}

function rotate() {
    var $container = $(this).parents('.package-image'),
        $angle     = $container.find('[id$=angle]'),
        $frame     = $container.find('.package-image-frame'),

        angle = parseInt($angle.val());
    
    // Rotate by 90 degrees clockwize
    angle = (angle + 90) % 360;

    // Save
    $angle.val(angle);

    // Display
    $frame.attr('rel', 'rotate-' + angle);
}

function duplicate() {
    var $source = $(this).parents('.package-image'),
        $copy   = $source.clone();

    // Management form
    var $formset = $source.parents('.package-images'),
        total    = parseInt($('input[id$=TOTAL_FORMS]', $formset).val());
    
    $('input[id$=TOTAL_FORMS]', $formset).val(total + 1);

    // $copy id is empty because it is not saved yet
    $('input[id$=id]', $copy).removeAttr('value');

    // $copy field names should be of format: IMAGES_N-X-fieldname
    var search = /-\d+-/,
        index  = '-' + String(total) + '-';
    
    // Fix id, name, and for attributes
    $('input, label', $copy).each(function(i, item) {
        if (item.name) {
            item.name = item.name.replace(search, index);
        }

        if (item.id) {
            item.id   = item.id.replace(search, index);
        }

        if ($(item).attr('for')) {
            $(item).attr(
                'for',
                $(item).attr('for').replace(search, index)
            );
        }
    });

    // Fix handlers
    $('[id$=thumbnail]', $copy).click(set_thumbnail);
    $('[id$=skipped]', $copy).click(set_skipped);

    // UI
    $('label', $copy).each(function(i, label) {
        $(label).html(
            $('.ui-button-text', $(label)).html()
        );
    });
    $('.package-buttons', $copy).buttonset();

    // Turn thumbnail off if it is set
    $copy.find('[id$=thumbnail]')[0].checked = false;
    $copy.find('[id$=thumbnail]').change();

    // Duplicate handler
    $('.package-duplicate', $copy).click(duplicate);
    $('.package-rotate', $copy).click(rotate);
    $('.package-zoom', $copy).fancybox(fancybox_options);
    
    // Show the source
    var id = $source.find('[id$=id]').val();
    if (id) {
        $copy.find('[id$=source]').val(id);
    }

    $source.after($copy);

    Sorter.init();
    //Sorter.update.apply($formset);
}

$(function() {
    // Buttons

    $ = django.jQuery;

    $('.package-buttons').buttonset();

    // There are some dependencies between different checkboxes.
    $('.package-buttons input[type="checkbox"][id$=is_thumbnail]').click(set_thumbnail);

    // If an image is skipped, it cannot be a thumbnail.
    $('.package-buttons input[type="checkbox"][id$=is_skipped]').click(set_skipped);

    // Color coding
    $('#changelist input.radiolist').change(function() {
        if (this.checked) {
            var colors = {
                'skipped': '#FBD850',
                'void': '#FB8350',
                'approved': '#50FB83',
            };

            var row = $(this).parents('tr')[0];
            row.style.backgroundColor = colors[this.value];
        }
    });

    // Initial coloring
    $('input.radiolist').change();

    // Refresh if no packages
    var href = $('ul.object-tools .selected a').attr('href');
    if (href && (href.indexOf('pending') !== -1)) {
        // We are on 'incoming images' screen. Is it empty?
        if (!($('#result_list tr.row1').length)) {
            // It really is!
            $('p.paginator').html($('p.paginator').html() + ' (The page will be reloaded in 30 sec.)')

            var sec = 1000;
            setTimeout(function() {
                location.reload();
            }, 30 * sec);
        }
    }

    fancybox_options = {
        closeBtn: false,
        arrows: false,
        closeClick: true,
    }

    $('.package-duplicate').click(duplicate);
    $('.package-rotate').click(rotate);
    $('.package-zoom').fancybox(fancybox_options);

    // Sort init
    Sorter.init();
});
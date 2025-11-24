CTFd.plugin.run((_CTFd) => {
    const $ = _CTFd.lib.$
    const md = _CTFd.lib.markdown()

    // Function to generate preview of dynamic flag
    function previewFlag(template) {
        if (!template) {
            return '';
        }
        // Replace <hex> with random 6-character hex values for preview
        var preview = template.replace(/<hex>/g, function() {
            return Math.random().toString(16).substr(2, 6);
        });
        return 'CYBERCOM{' + preview + '}';
    }

    $(document).ready(function() {
        $.getJSON("/api/v1/docker", function(result) {
            $.each(result['data'], function(i, item) {
                $("#dockerimage_select").append($("<option />").val(item.name).text(item.name));
            });
            $("#dockerimage_select").val(DOCKER_IMAGE).change();
        });

        // Show flag preview on input change
        $('#flag_template').on('input', function() {
            var template = $(this).val();
            if (template && template.trim() !== '') {
                var preview = previewFlag(template);
                $('#flag_preview_text').text(preview);
                $('#flag_preview').show();
            } else {
                $('#flag_preview').hide();
            }
        });

        // Trigger preview on page load with current value
        if ($('#flag_template').val()) {
            $('#flag_template').trigger('input');
        }
    });
});
CTFd.plugin.run((_CTFd) => {
    const $ = _CTFd.lib.$
    const md = _CTFd.lib.markdown()
    $('a[href="#new-desc-preview"]').on('shown.bs.tab', function (event) {
        if (event.target.hash == '#new-desc-preview') {
            var editor_value = $('#new-desc-editor').val();
            $(event.target.hash).html(
                md.render(editor_value)
            );
        }
    });

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

    $(document).ready(function(){
    $('[data-toggle="tooltip"]').tooltip();
    $.getJSON("/api/v1/docker", function(result){
        $.each(result['data'], function(i, item){
            if (item.name == 'Error in Docker Config!') {
                document.docker_form.dockerimage_select.disabled = true;
                $("label[for='DockerImage']").text('Docker Image ' + item.name)
            }
            else {
                $("#dockerimage_select").append($("<option />").val(item.name).text(item.name));
            }
        });
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

    // Trigger preview on page load with default value
    if ($('#flag_template').val()) {
        $('#flag_template').trigger('input');
    }
});
});
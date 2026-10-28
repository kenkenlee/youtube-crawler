// Settings page JavaScript

$(document).ready(function() {
    // Show/hide provider fields when the provider radio changes
    $('input[name="llmProvider"]').change(function() {
        showProviderFields($(this).val());
    });

    loadSettings();
});

function showProviderFields(provider) {
    $('.provider-fields').addClass('d-none');
    if (provider === 'openrouter') $('#openrouterFields').removeClass('d-none');
    else if (provider === 'deepseek') $('#deepseekFields').removeClass('d-none');
    else if (provider === 'openai') $('#openaiFields').removeClass('d-none');
}

function togglePassword(inputId, btn) {
    const $input = $('#' + inputId);
    const isPassword = $input.attr('type') === 'password';
    $input.attr('type', isPassword ? 'text' : 'password');
    btn.innerHTML = isPassword ? '<i class="bi bi-eye-slash"></i>' : '<i class="bi bi-eye"></i>';
}

function loadSettings() {
    $.get('/api/settings', function(s) {
        $('#youtubeApiKey').val(s.youtube_api_key || '');
        $('#autoFetchTranscript').prop('checked', !!s.auto_fetch_transcript);
        $('#autoSummarize').prop('checked', !!s.auto_summarize);
        $('#maxVideosPerChannel').val(s.max_videos_per_channel ?? 30);
        $('#crawlDelaySeconds').val(s.crawl_delay_seconds ?? 1);

        // Provider selection
        const provider = s.llm_provider || 'openrouter';
        $(`input[name="llmProvider"][value="${provider}"]`).prop('checked', true);
        showProviderFields(provider);

        $('#openrouterApiKey').val(s.openrouter_api_key || '');
        $('#openrouterBaseUrl').val(s.openrouter_base_url || '');
        $('#openrouterModel').val(s.openrouter_model || '');
        $('#deepseekApiKey').val(s.deepseek_api_key || '');
        $('#deepseekBaseUrl').val(s.deepseek_base_url || '');
        $('#deepseekModel').val(s.deepseek_model || '');
        $('#openaiApiKey').val(s.openai_api_key || '');
        $('#openaiModel').val(s.openai_model || '');
    }).fail(function(xhr) {
        if (xhr.status === 401) { redirectToLogin(); return; }
        showToast('Failed to load settings', false);
    });
}

function saveSettings() {
    const provider = $('input[name="llmProvider"]:checked').val() || 'openrouter';

    const payload = {
        YOUTUBE_API_KEY: $('#youtubeApiKey').val().trim(),
        LLM_PROVIDER: provider,
        OPENROUTER_API_KEY: $('#openrouterApiKey').val().trim(),
        OPENROUTER_BASE_URL: $('#openrouterBaseUrl').val().trim(),
        OPENROUTER_MODEL: $('#openrouterModel').val().trim(),
        DEEPSEEK_API_KEY: $('#deepseekApiKey').val().trim(),
        DEEPSEEK_BASE_URL: $('#deepseekBaseUrl').val().trim(),
        DEEPSEEK_MODEL: $('#deepseekModel').val().trim(),
        OPENAI_API_KEY: $('#openaiApiKey').val().trim(),
        OPENAI_MODEL: $('#openaiModel').val().trim(),
        AUTO_FETCH_TRANSCRIPT: $('#autoFetchTranscript').is(':checked'),
        AUTO_SUMMARIZE: $('#autoSummarize').is(':checked'),
        MAX_VIDEOS_PER_CHANNEL: parseInt($('#maxVideosPerChannel').val(), 10) || 30,
        CRAWL_DELAY_SECONDS: parseInt($('#crawlDelaySeconds').val(), 10) || 0
    };

    const $btn = $('#saveSettingsBtn');
    const original = $btn.html();
    $btn.html('<span class="spinner-border spinner-border-sm me-2"></span>Saving...').prop('disabled', true);

    $.ajax({
        url: '/api/settings',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(payload),
        success: function() {
            showToast('Settings saved successfully', true);
            $btn.html(original).prop('disabled', false);
        },
        error: function(xhr) {
            if (xhr.status === 401) { redirectToLogin(); return; }
            showToast('Failed to save settings: ' + (xhr.responseJSON?.detail || 'Unknown error'), false);
            $btn.html(original).prop('disabled', false);
        }
    });
}

function changePassword() {
    const current = $('#currentPassword').val();
    const next = $('#newPassword').val();
    const confirm = $('#confirmPassword').val();

    if (!current || !next || !confirm) {
        showToast('Please fill in all password fields', false);
        return;
    }
    if (next !== confirm) {
        showToast('New password and confirmation do not match', false);
        return;
    }

    const $btn = $('#changePasswordBtn');
    const original = $btn.html();
    $btn.html('<span class="spinner-border spinner-border-sm me-2"></span>Changing...').prop('disabled', true);

    $.ajax({
        url: '/api/settings/change-password',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ current_password: current, new_password: next }),
        success: function() {
            showToast('Password updated successfully', true);
            $('#currentPassword').val('');
            $('#newPassword').val('');
            $('#confirmPassword').val('');
            $btn.html(original).prop('disabled', false);
        },
        error: function(xhr) {
            if (xhr.status === 401) { redirectToLogin(); return; }
            showToast('Failed to change password: ' + (xhr.responseJSON?.detail || 'Unknown error'), false);
            $btn.html(original).prop('disabled', false);
        }
    });
}

function redirectToLogin() {
    window.location.href = '/settings/login';
}

function showToast(message, success) {
    const $toast = $('#settingsToast');
    $('#settingsToastBody').text(message);
    $toast.removeClass('text-bg-success text-bg-danger').addClass(success ? 'text-bg-success' : 'text-bg-danger');
    const toast = new bootstrap.Toast($toast[0], { delay: 3000 });
    toast.show();
}

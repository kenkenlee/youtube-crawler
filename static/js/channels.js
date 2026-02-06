// Channels Management JavaScript

$(document).ready(function() {
    loadChannels();

    // Filter by active only
    $('#showActiveOnly').change(function() {
        loadChannels();
    });
});

function loadChannels() {
    const showActiveOnly = $('#showActiveOnly').is(':checked');
    const url = showActiveOnly ? '/api/channels?crawl_enabled=true' : '/api/channels';

    $.get(url, function(data) {
        const container = $('#channelsList');
        container.empty();

        if (data.length === 0) {
            container.html('<p class="text-muted">No channels found. Add your first channel to get started!</p>');
            return;
        }

        data.forEach(function(channel) {
            const channelCard = createChannelCard(channel);
            container.append(channelCard);
        });
    }).fail(function() {
        $('#channelsList').html('<p class="text-danger">Failed to load channels</p>');
    });
}

function createChannelCard(channel) {
    const statusBadge = channel.crawl_enabled
        ? '<span class="badge bg-success">Active</span>'
        : '<span class="badge bg-secondary">Inactive</span>';

    const lastCrawled = channel.last_crawled_at
        ? new Date(channel.last_crawled_at).toLocaleString()
        : 'Never';

    const keywords = channel.keywords && channel.keywords.length > 0
        ? channel.keywords.map(k => `<span class="badge bg-info me-1">${k}</span>`).join('')
        : '<span class="text-muted small">No keywords</span>';

    // Use the thumbnail_url from database if available, otherwise use fallback
    const channelIconUrl = channel.thumbnail_url ||
        'https://www.gstatic.com/youtube/img/branding/youtubelogo/svg/youtubelogo.svg';

    return `
        <div class="channel-card-compact">
            <div class="d-flex align-items-center">
                <img src="${channelIconUrl}"
                     class="channel-icon me-3"
                     alt="${channel.channel_name}"
                     onerror="this.src='https://www.gstatic.com/youtube/img/branding/youtubelogo/svg/youtubelogo.svg'">
                <div class="flex-grow-1">
                    <div class="d-flex justify-content-between align-items-start mb-1">
                        <div>
                            <h6 class="channel-name-compact mb-1">${channel.channel_name}</h6>
                            <div class="channel-meta">
                                ${statusBadge}
                                <span class="badge bg-primary ms-1">${channel.crawl_frequency}</span>
                                <span class="text-muted small ms-2">
                                    <i class="bi bi-play-circle"></i> ${channel.video_count} videos
                                    <span class="text-success">(${channel.summarized_count} summarized)</span>
                                </span>
                            </div>
                        </div>
                        <div class="btn-group btn-group-sm">
                            <button class="btn btn-sm btn-outline-primary" onclick="viewChannel(${channel.id})" title="View Videos">
                                <i class="bi bi-collection-play"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-secondary" onclick="editChannel(${channel.id})" title="Edit">
                                <i class="bi bi-pencil"></i>
                            </button>
                            <button class="btn btn-sm btn-outline-danger" onclick="deleteChannel(${channel.id}, '${channel.channel_name}')" title="Delete">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    </div>
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="channel-keywords">${keywords}</div>
                        <div class="d-flex gap-2">
                            <small class="text-muted">Last: ${lastCrawled}</small>
                            <a href="${channel.channel_url}" target="_blank" class="btn btn-sm btn-outline-secondary" title="View on YouTube">
                                <i class="bi bi-youtube"></i>
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function addChannel() {
    const channelId = $('#channelId').val().trim();
    const channelName = $('#channelName').val().trim();
    const channelUrl = $('#channelUrl').val().trim();
    const description = $('#channelDescription').val().trim();
    const keywords = $('#channelKeywords').val();
    const crawlFrequency = $('#crawlFrequency').val();
    const crawlEnabled = $('#crawlEnabled').is(':checked');

    // Validate required fields
    if (!channelId || !channelName || !channelUrl) {
        alert('Please fill in all required fields (Reference ID, Channel Name, and URL)');
        return;
    }

    // Validate reference ID format (alphanumeric and hyphens only)
    if (!/^[a-zA-Z0-9-_]+$/.test(channelId)) {
        alert('Reference ID can only contain letters, numbers, hyphens, and underscores');
        return;
    }

    const keywordsList = keywords ? keywords.split(',').map(k => k.trim()).filter(k => k) : [];

    const payload = {
        channel_id: channelId,
        youtube_channel_id: null,  // Will be auto-extracted if needed
        channel_name: channelName,
        channel_url: channelUrl,
        description: description,
        keywords: keywordsList,
        crawl_enabled: crawlEnabled,
        crawl_frequency: crawlFrequency
    };

    $.ajax({
        url: '/api/channels',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(payload),
        success: function(response) {
            alert('Channel added successfully!');
            $('#addChannelModal').modal('hide');
            $('#addChannelForm')[0].reset();
            loadChannels();
        },
        error: function(xhr) {
            if (xhr.status === 400 && xhr.responseJSON?.detail?.includes('already exists')) {
                alert('A channel with this Reference ID already exists. Please use a different ID.');
            } else {
                alert('Failed to add channel: ' + (xhr.responseJSON?.detail || 'Unknown error'));
            }
        }
    });
}

function extractChannelId(url) {
    // Try multiple URL formats

    // Format 1: /channel/UCxxxxxx
    let match = url.match(/youtube\.com\/channel\/(UC[\w-]+)/);
    if (match) return match[1];

    // Format 2: /c/channelname or /@username - return null to use API
    match = url.match(/youtube\.com\/(c\/|@)([\w-]+)/);
    if (match) return null; // Let backend handle these

    // Format 3: /user/username - return null to use API
    match = url.match(/youtube\.com\/user\/([\w-]+)/);
    if (match) return null; // Let backend handle these

    // Format 4: Just the channel ID
    match = url.match(/^(UC[\w-]+)$/);
    if (match) return match[1];

    return null;
}

function addChannelFromUrl(channelUrl, channelName, description, keywords, crawlFrequency, crawlEnabled) {
    // Use the from-url endpoint which handles all URL formats
    const keywordsList = keywords ? keywords.split(',').map(k => k.trim()).filter(k => k) : [];

    // Show loading message
    const originalText = $('#addChannelModal .btn-primary').text();
    $('#addChannelModal .btn-primary').text('Fetching channel info...').prop('disabled', true);

    $.ajax({
        url: '/api/channels/from-url',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ url: channelUrl }),
        success: function(response) {
            // Channel created successfully, now update it with user's settings
            const channelId = response.id;

            const updatePayload = {
                channel_name: channelName,
                description: description,
                keywords: keywordsList,
                crawl_enabled: crawlEnabled,
                crawl_frequency: crawlFrequency
            };

            $.ajax({
                url: `/api/channels/${channelId}`,
                method: 'PUT',
                contentType: 'application/json',
                data: JSON.stringify(updatePayload),
                success: function() {
                    alert('Channel added successfully!');
                    $('#addChannelModal').modal('hide');
                    $('#addChannelForm')[0].reset();
                    $('#addChannelModal .btn-primary').text(originalText).prop('disabled', false);
                    loadChannels();
                },
                error: function(xhr) {
                    alert('Channel added but failed to update settings: ' + (xhr.responseJSON?.detail || 'Unknown error'));
                    $('#addChannelModal').modal('hide');
                    $('#addChannelForm')[0].reset();
                    $('#addChannelModal .btn-primary').text(originalText).prop('disabled', false);
                    loadChannels();
                }
            });
        },
        error: function(xhr) {
            $('#addChannelModal .btn-primary').text(originalText).prop('disabled', false);

            if (xhr.status === 400 && xhr.responseJSON?.detail?.includes('already exists')) {
                alert('This channel already exists in your database.');
            } else if (xhr.status === 400) {
                alert('Could not extract channel ID from URL. Please check the URL or provide the channel ID manually.');
            } else if (xhr.status === 404) {
                alert('Channel not found on YouTube. Please check the URL.');
            } else {
                alert('Failed to add channel: ' + (xhr.responseJSON?.detail || 'Unknown error'));
            }
        }
    });
}

function viewChannel(channelId) {
    window.location.href = `/videos?channel_id=${channelId}`;
}

function editChannel(channelId) {
    // Load channel data
    $.get(`/api/channels/${channelId}`, function(channel) {
        $('#editChannelId').val(channel.id);
        $('#editChannelName').val(channel.channel_name);
        $('#editChannelDescription').val(channel.description || '');
        $('#editChannelKeywords').val(channel.keywords ? channel.keywords.join(', ') : '');
        $('#editCrawlFrequency').val(channel.crawl_frequency);
        $('#editCrawlEnabled').prop('checked', channel.crawl_enabled);

        $('#editChannelModal').modal('show');
    }).fail(function() {
        alert('Failed to load channel data');
    });
}

function updateChannel() {
    const channelId = $('#editChannelId').val();
    const channelName = $('#editChannelName').val();
    const description = $('#editChannelDescription').val();
    const keywords = $('#editChannelKeywords').val();
    const crawlFrequency = $('#editCrawlFrequency').val();
    const crawlEnabled = $('#editCrawlEnabled').is(':checked');

    const keywordsList = keywords ? keywords.split(',').map(k => k.trim()).filter(k => k) : [];

    const payload = {
        channel_name: channelName,
        description: description,
        keywords: keywordsList,
        crawl_enabled: crawlEnabled,
        crawl_frequency: crawlFrequency
    };

    $.ajax({
        url: `/api/channels/${channelId}`,
        method: 'PUT',
        contentType: 'application/json',
        data: JSON.stringify(payload),
        success: function(response) {
            alert('Channel updated successfully!');
            $('#editChannelModal').modal('hide');
            loadChannels();
        },
        error: function(xhr) {
            alert('Failed to update channel: ' + (xhr.responseJSON?.detail || 'Unknown error'));
        }
    });
}

function deleteChannel(channelId, channelName) {
    if (!confirm(`Are you sure you want to delete "${channelName}"? This will also delete all associated videos.`)) {
        return;
    }

    $.ajax({
        url: `/api/channels/${channelId}`,
        method: 'DELETE',
        success: function() {
            alert('Channel deleted successfully!');
            loadChannels();
        },
        error: function(xhr) {
            alert('Failed to delete channel: ' + (xhr.responseJSON?.detail || 'Unknown error'));
        }
    });
}

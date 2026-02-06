// Videos Management JavaScript

let currentPage = 0;
let currentVideoId = null;

$(document).ready(function() {
    // Get URL parameters FIRST
    const urlParams = new URLSearchParams(window.location.search);
    const channelId = urlParams.get('channel_id');
    const sessionId = urlParams.get('session_id');

    // Store the channel filter from URL
    if (channelId) {
        $('#channelFilter').val(channelId);
        // Store in a global variable to persist the filter
        window.currentChannelFilter = channelId;
    }

    // THEN load videos and channels filter
    loadVideos();
    loadChannelsFilter();

    // Search on Enter key
    $('#searchQuery').keypress(function(e) {
        if (e.which === 13) {
            searchVideos();
        }
    });

    // When channel filter changes, update the URL
    $('#channelFilter').change(function() {
        const selectedChannel = $(this).val();
        if (selectedChannel) {
            window.currentChannelFilter = selectedChannel;
            // Update URL without reloading
            const newUrl = new URL(window.location);
            newUrl.searchParams.set('channel_id', selectedChannel);
            window.history.pushState({}, '', newUrl);
        } else {
            window.currentChannelFilter = null;
            // Remove channel_id from URL
            const newUrl = new URL(window.location);
            newUrl.searchParams.delete('channel_id');
            window.history.pushState({}, '', newUrl);
        }
        loadVideos();
    });
});

function loadVideos(page = 0) {
    const limit = 20;
    const skip = page * limit;
    // Use the stored channel filter or get from dropdown
    const channelId = window.currentChannelFilter || $('#channelFilter').val();
    const hasSummary = $('#summaryFilter').val();

    let url = `/api/videos?skip=${skip}&limit=${limit}`;
    if (channelId) url += `&channel_id=${channelId}`;
    if (hasSummary) url += `&has_summary=${hasSummary}`;

    $.get(url, function(data) {
        displayVideos(data);
        currentPage = page;
    }).fail(function() {
        $('#videosList').html('<p class="text-danger">Failed to load videos</p>');
    });
}

function searchVideos() {
    const query = $('#searchQuery').val();
    if (!query || query.trim() === '') {
        loadVideos();
        return;
    }

    // Include channel filter in search if present
    const channelId = window.currentChannelFilter || $('#channelFilter').val();
    let url = `/api/videos/search?q=${encodeURIComponent(query)}`;
    if (channelId) {
        url += `&channel_id=${channelId}`;
    }

    $.get(url, function(data) {
        displayVideos(data);
    }).fail(function() {
        $('#videosList').html('<p class="text-danger">Search failed</p>');
    });
}

function displayVideos(videos) {
    const container = $('#videosList');
    container.empty();

    if (videos.length === 0) {
        container.html('<p class="text-muted">No videos found</p>');
        return;
    }

    videos.forEach(function(video) {
        const videoCard = createVideoCard(video);
        container.append(videoCard);
    });
}

function createVideoCard(video) {
    const publishedDate = video.published_at
        ? new Date(video.published_at).toLocaleDateString()
        : 'Unknown';

    const duration = formatDuration(video.duration);
    const views = formatNumber(video.view_count);
    const likes = formatNumber(video.like_count);

    const summaryBadge = video.summary_text
        ? '<span class="badge bg-success"><i class="bi bi-check-circle"></i> Summarized</span>'
        : '<span class="badge bg-warning"><i class="bi bi-clock"></i> No Summary</span>';

    const keywords = video.matched_keywords && video.matched_keywords.length > 0
        ? video.matched_keywords.map(k => `<span class="badge bg-info me-1">${k}</span>`).join('')
        : '';

    const channelName = video.channel_name || 'Unknown Channel';
    const videoUrl = `https://www.youtube.com/watch?v=${video.video_id}`;

    return `
        <div class="video-card fade-in">
            <img src="https://img.youtube.com/vi/${video.video_id}/mqdefault.jpg"
                 alt="${video.title}"
                 class="video-thumbnail"
                 onerror="this.src='https://via.placeholder.com/120x90?text=No+Image'">
            <div class="video-info">
                <h6 class="video-title">${video.title}</h6>
                <p class="video-meta mb-2">
                    <i class="bi bi-collection-play"></i> ${channelName} &nbsp;|&nbsp;
                    <i class="bi bi-calendar"></i> ${publishedDate} &nbsp;|&nbsp;
                    <i class="bi bi-clock"></i> ${duration} &nbsp;|&nbsp;
                    <i class="bi bi-eye"></i> ${views} views &nbsp;|&nbsp;
                    <i class="bi bi-hand-thumbs-up"></i> ${likes}
                </p>
                ${keywords ? `<div class="mb-2">${keywords}</div>` : ''}
                <div class="mb-2">${summaryBadge}</div>
                ${video.summary_text ? `
                <div class="mb-2">
                    <strong>Summary:</strong>
                    <p class="text-truncate-3">${video.summary_text}</p>
                </div>
                ` : ''}
                <div class="btn-group">
                    <button class="btn btn-sm btn-primary" onclick="viewVideoDetails(${video.id})">
                        <i class="bi bi-eye"></i> View Details
                    </button>
                    <a href="${videoUrl}" target="_blank" class="btn btn-sm btn-outline-danger">
                        <i class="bi bi-youtube"></i> Watch on YouTube
                    </a>
                    ${!video.transcript_text ? `
                    <button class="btn btn-sm btn-outline-warning" onclick="fetchTranscript(${video.id})">
                        <i class="bi bi-file-text"></i> Get Transcript
                    </button>
                    ` : ''}
                    ${!video.summary_text ? `
                    <button class="btn btn-sm btn-outline-success" onclick="generateSummary(${video.id})">
                        <i class="bi bi-magic"></i> Generate Summary
                    </button>
                    ` : ''}
                    <button class="btn btn-sm btn-outline-info" onclick="downloadVideo(${video.id}, '${video.video_id}', '${video.title.replace(/'/g, "\\'")}')">
                        <i class="bi bi-download"></i> Download
                    </button>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteVideo(${video.id})">
                        <i class="bi bi-trash"></i> Delete
                    </button>
                </div>
            </div>
        </div>
    `;
}

function loadChannelsFilter() {
    $.get('/api/channels?limit=100', function(data) {
        const select = $('#channelFilter');
        select.find('option:not(:first)').remove();

        data.forEach(function(channel) {
            select.append(`<option value="${channel.id}">${channel.channel_name}</option>`);
        });
    });
}

function viewVideoDetails(videoId) {
    currentVideoId = videoId;

    $.get(`/api/videos/${videoId}`, function(video) {
        $('#videoDetailsTitle').text(video.title);

        const publishedDate = video.published_at
            ? new Date(video.published_at).toLocaleString()
            : 'Unknown';

        const duration = formatDuration(video.duration);
        const videoUrl = `https://www.youtube.com/watch?v=${video.video_id}`;

        const tags = video.tags && video.tags.length > 0
            ? video.tags.map(t => `<span class="badge bg-secondary me-1">${t}</span>`).join('')
            : '<span class="text-muted">No tags</span>';

        const keywords = video.matched_keywords && video.matched_keywords.length > 0
            ? video.matched_keywords.map(k => `<span class="badge bg-info me-1">${k}</span>`).join('')
            : '<span class="text-muted">No matched keywords</span>';

        const content = `
            <div class="row">
                <div class="col-md-6">
                    <div class="ratio ratio-16x9 mb-3">
                        <iframe src="https://www.youtube.com/embed/${video.video_id}"
                                allowfullscreen></iframe>
                    </div>
                </div>
                <div class="col-md-6">
                    <h6>Video Information</h6>
                    <table class="table table-sm">
                        <tr><td><strong>Channel:</strong></td><td>${video.channel_name}</td></tr>
                        <tr><td><strong>Published:</strong></td><td>${publishedDate}</td></tr>
                        <tr><td><strong>Duration:</strong></td><td>${duration}</td></tr>
                        <tr><td><strong>Views:</strong></td><td>${formatNumber(video.view_count)}</td></tr>
                        <tr><td><strong>Likes:</strong></td><td>${formatNumber(video.like_count)}</td></tr>
                        <tr><td><strong>Comments:</strong></td><td>${formatNumber(video.comment_count)}</td></tr>
                    </table>
                    <div class="mb-2">
                        <strong>Tags:</strong><br>${tags}
                    </div>
                    <div class="mb-2">
                        <strong>Matched Keywords:</strong><br>${keywords}
                    </div>
                    <a href="${videoUrl}" target="_blank" class="btn btn-danger">
                        <i class="bi bi-youtube"></i> Watch on YouTube
                    </a>
                </div>
            </div>
            <div class="row mt-3">
                <div class="col-12">
                    <h6>Description</h6>
                    <p>${video.description || 'No description available'}</p>
                </div>
            </div>
            ${video.summary_text ? `
            <div class="row mt-3">
                <div class="col-12">
                    <h6>AI Summary</h6>
                    <div class="alert alert-info">
                        ${video.summary_text}
                    </div>
                    <small class="text-muted">
                        Generated: ${video.summary_generated_at ? new Date(video.summary_generated_at).toLocaleString() : 'Unknown'}
                    </small>
                </div>
            </div>
            ` : `
            <div class="row mt-3">
                <div class="col-12">
                    <div class="alert alert-warning">
                        <i class="bi bi-exclamation-triangle"></i> No summary available for this video.
                        Click "Generate Summary" to create one.
                    </div>
                </div>
            </div>
            `}
            ${video.transcript_text ? `
            <div class="row mt-3">
                <div class="col-12">
                    <h6>Transcript</h6>
                    <div class="bg-light p-3 rounded" style="max-height: 300px; overflow-y: auto;">
                        <pre style="white-space: pre-wrap;">${video.transcript_text}</pre>
                    </div>
                </div>
            </div>
            ` : ''}
        `;

        $('#videoDetailsContent').html(content);
        $('#videoDetailsModal').modal('show');
    }).fail(function() {
        alert('Failed to load video details');
    });
}

function generateSummary(videoId) {
    if (!confirm('Generate AI summary for this video?')) {
        return;
    }

    $.ajax({
        url: `/api/videos/${videoId}/summarize`,
        method: 'POST',
        success: function(response) {
            alert('Summary generation started! This may take a few moments.');
            setTimeout(() => loadVideos(currentPage), 3000);
        },
        error: function(xhr) {
            alert('Failed to generate summary: ' + (xhr.responseJSON?.detail || 'Unknown error'));
        }
    });
}

function regenerateSummary() {
    if (!currentVideoId) return;

    if (!confirm('Regenerate AI summary for this video?')) {
        return;
    }

    $.ajax({
        url: `/api/videos/${currentVideoId}/summarize?force_regenerate=true`,
        method: 'POST',
        success: function(response) {
            alert('Summary regeneration started!');
            $('#videoDetailsModal').modal('hide');
            setTimeout(() => loadVideos(currentPage), 3000);
        },
        error: function(xhr) {
            alert('Failed to regenerate summary: ' + (xhr.responseJSON?.detail || 'Unknown error'));
        }
    });
}

function deleteVideo(videoId) {
    if (!confirm('Are you sure you want to delete this video? This action cannot be undone.')) {
        return;
    }

    $.ajax({
        url: `/api/videos/${videoId}`,
        method: 'DELETE',
        success: function() {
            alert('Video deleted successfully!');
            loadVideos(currentPage);
        },
        error: function(xhr) {
            alert('Failed to delete video: ' + (xhr.responseJSON?.detail || 'Unknown error'));
        }
    });
}

function downloadVideo(videoId, youtubeVideoId, title) {
    if (!confirm(`Download video: ${title}?`)) {
        return;
    }

    // Show downloading message
    alert('Starting download... This may take a few moments. The download will begin automatically.');

    // Create a temporary link to trigger download
    const downloadUrl = `/api/videos/${videoId}/download`;

    // Open in new window to trigger download
    window.open(downloadUrl, '_blank');
}

function fetchTranscript(videoId) {
    if (!confirm('Fetch transcript for this video?')) {
        return;
    }

    $.ajax({
        url: `/api/videos/${videoId}/transcript`,
        method: 'GET',
        success: function(response) {
            alert('Transcript fetched successfully!');
            loadVideos(currentPage);
        },
        error: function(xhr) {
            alert('Failed to fetch transcript: ' + (xhr.responseJSON?.detail || 'Unknown error'));
        }
    });
}

function exportVideos() {
    alert('Export functionality coming soon!');
    // TODO: Implement export to Excel/CSV
}

function formatDuration(seconds) {
    if (!seconds) return '0:00';

    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

function formatNumber(num) {
    if (!num) return '0';
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
}

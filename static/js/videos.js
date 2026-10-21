// Videos Management JavaScript

let currentPage = 0;
let currentVideoId = null;
let currentViewMode = 'list';  // 'list' (detailed) or 'browse' (thumbnail + short info)
let currentVideos = [];        // last loaded videos (for re-render on row-size change)

function setViewMode(mode) {
    currentViewMode = mode;
    $('#viewListBtn').toggleClass('active', mode === 'list');
    $('#viewBrowseBtn').toggleClass('active', mode === 'browse');
    // Row-size selector only applies to the browse view
    $('#browseRowSize').closest('.col-md-1').toggle(mode === 'browse');
    loadVideos();
}

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

    // When sort option changes, reload videos
    $('#sortFilter').change(function() {
        loadVideos();
    });

    // When sort direction changes, reload videos
    $('#orderFilter').change(function() {
        loadVideos();
    });

    // Browse view row-size selector: visible only in browse mode
    $('#browseRowSize').change(function() {
        if (currentViewMode === 'browse') {
            displayVideos(currentVideos);
        }
    });
});

function loadVideos(page = 0) {
    const limit = 50;  // Increased from 20 to 50
    const skip = page * limit;
    // Use the stored channel filter or get from dropdown
    const channelId = window.currentChannelFilter || $('#channelFilter').val();
    const hasSummary = $('#summaryFilter').val();
    const sortBy = $('#sortFilter').val() || 'fetched';
    const order = $('#orderFilter').val() || 'desc';

    let url = `/api/videos?skip=${skip}&limit=${limit}&sort_by=${sortBy}&order=${order}`;
    if (channelId) url += `&channel_id=${channelId}`;
    if (hasSummary) url += `&has_summary=${hasSummary}`;

    $.get(url, function(data) {
        currentVideos = data;
        displayVideos(data);
        currentPage = page;
        updatePagination(data.length, limit, page);
    }).fail(function() {
        $('#videosList').html('<p class="text-danger">Failed to load videos</p>');
    });
}

function updatePagination(itemCount, limit, currentPage) {
    const hasMore = itemCount === limit;
    const hasPrevious = currentPage > 0;

    let paginationHtml = '<nav aria-label="Video pagination"><ul class="pagination justify-content-center mt-4">';

    // Previous button
    if (hasPrevious) {
        paginationHtml += `<li class="page-item"><a class="page-link" href="#" onclick="loadVideos(${currentPage - 1}); return false;">Previous</a></li>`;
    } else {
        paginationHtml += '<li class="page-item disabled"><span class="page-link">Previous</span></li>';
    }

    // Page numbers (show current and nearby pages)
    const startPage = Math.max(0, currentPage - 2);
    const endPage = currentPage + 2;

    for (let i = startPage; i <= endPage; i++) {
        if (i === currentPage) {
            paginationHtml += `<li class="page-item active"><span class="page-link">${i + 1}</span></li>`;
        } else {
            paginationHtml += `<li class="page-item"><a class="page-link" href="#" onclick="loadVideos(${i}); return false;">${i + 1}</a></li>`;
        }
    }

    // Next button
    if (hasMore) {
        paginationHtml += `<li class="page-item"><a class="page-link" href="#" onclick="loadVideos(${currentPage + 1}); return false;">Next</a></li>`;
    } else {
        paginationHtml += '<li class="page-item disabled"><span class="page-link">Next</span></li>';
    }

    paginationHtml += '</ul></nav>';

    // Add or update pagination
    $('#videoPagination').remove();
    $('#videosList').after(`<div id="videoPagination">${paginationHtml}</div>`);
}

function searchVideos() {
    const query = $('#searchQuery').val();
    if (!query || query.trim() === '') {
        loadVideos();
        return;
    }

    // Include channel filter in search if present; keep the chosen sort order
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

    if (currentViewMode === 'browse') {
        displayBrowseView(videos);
        return;
    }

    videos.forEach(function(video) {
        const videoCard = createVideoCard(video);
        container.append(videoCard);
    });
}

// Browse view: videos grouped row-by-row per channel, each video showing
// only thumbnail, title and short info. Number of videos per row is
// configurable (default 5) via the row-size selector.
function displayBrowseView(videos) {
    const container = $('#videosList');
    const colsPerRow = parseInt($('#browseRowSize').val() || '5', 10);

    // Group videos by channel preserving the current sort order
    const byChannel = new Map();
    videos.forEach(function(video) {
        const key = video.channel_name || 'Unknown Channel';
        if (!byChannel.has(key)) {
            byChannel.set(key, { channel: video, videos: [] });
        }
        byChannel.get(key).videos.push(video);
    });

    byChannel.forEach(function(group, channelName) {
        const channelVideo = group.channel;
        const logoUrl = channelVideo.channel_thumbnail_url;
        const logoImg = logoUrl
            ? `<img src="${logoUrl}" class="rounded-circle me-2" width="32" height="32"
                     alt="${channelName}"
                     onerror="this.onerror=null;this.src='https://ui-avatars.com/api/?name=${encodeURIComponent(channelName.charAt(0))}&background=ff0000&color=fff';">`
            : `<img src="https://ui-avatars.com/api/?name=${encodeURIComponent(channelName.charAt(0))}&background=ff0000&color=fff"
                     class="rounded-circle me-2" width="32" height="32"
                     alt="${channelName}"
                     onerror="this.style.display='none'">`;
        const channelSection = `
        <div class="card mb-4">
            <div class="card-header bg-light d-flex align-items-center">
                ${logoImg}
                <h5 class="mb-0 me-2">${channelName}</h5>
                <span class="badge bg-secondary">${group.videos.length} video${group.videos.length !== 1 ? 's' : ''}</span>
            </div>
            <div class="card-body">
                <div class="row row-cols-1 row-cols-md-${Math.min(colsPerRow, 6)} row-cols-lg-${colsPerRow} g-3">
                    ${group.videos.map(video => createBrowseCard(video)).join('')}
                </div>
            </div>
        </div>`;
        container.append(channelSection);
    });
}

function createBrowseCard(video) {
    const publishedDate = video.published_at
        ? new Date(video.published_at).toLocaleDateString()
        : 'Unknown';
    const fetchedDate = video.created_at
        ? new Date(video.created_at).toLocaleDateString()
        : 'Unknown';
    const duration = formatDuration(video.duration);
    const views = formatNumber(video.view_count);
    const summaryBadge = video.summary_text
        ? '<span class="badge bg-success"><i class="bi bi-check-circle"></i> Summary</span>'
        : '';
    const videoUrl = `https://www.youtube.com/watch?v=${video.video_id}`;

    return `
        <div class="col">
            <div class="card h-100 browse-card" onclick="viewVideoDetails(${video.id})" style="cursor:pointer">
                <img src="https://img.youtube.com/vi/${video.video_id}/mqdefault.jpg"
                     alt="${video.title}"
                     class="card-img-top browse-thumbnail"
                     onerror="this.src='https://via.placeholder.com/320x180?text=No+Image'">
                <div class="card-body p-2">
                    <h6 class="card-title mb-1 browse-title" title="${video.title}">${video.title}</h6>
                    <small class="text-muted d-block mb-1">
                        <i class="bi bi-calendar"></i> ${publishedDate} &middot;
                        <i class="bi bi-clock"></i> ${duration}
                    </small>
                    <small class="text-muted d-block">
                        <i class="bi bi-eye"></i> ${views} views
                        &middot; <i class="bi bi-cloud-download"></i> Fetched ${fetchedDate}
                    </small>
                    <div class="mt-1">${summaryBadge}</div>
                </div>
            </div>
        </div>
    `;
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
                ${video.summary_text ? `
                <div class="mb-3 p-3 bg-light border-start border-4 border-success">
                    <div class="d-flex align-items-center mb-2">
                        <i class="bi bi-stars text-success me-2"></i>
                        <strong class="text-success">AI Summary</strong>
                    </div>
                    <p class="mb-0 text-dark">${video.summary_text}</p>
                </div>
                ` : `
                <div class="mb-2">${summaryBadge}</div>
                `}
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
                    ${video.transcript_text && !video.detail_summary ? `
                    <button class="btn btn-sm btn-outline-success" onclick="generateDetailSummary(${video.id}, false)">
                        <i class="bi bi-file-earmark-text"></i> Detail Summary
                    </button>
                    ` : ''}
                    ${video.detail_summary ? `
                    <button class="btn btn-sm btn-purple" onclick="viewMindMap(${video.id})">
                        <i class="bi bi-diagram-3"></i> Mind Map
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

// Escape a string for safe use inside an HTML attribute (single/double quotes).
function escAttr(s) {
    return String(s || '')
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function viewVideoDetails(videoId, afterRender) {
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

        // Feature 4.1 / 5 / 6: action buttons — get transcript, generate detail
        // summary (only enabled when a transcript exists), mind map (only shown
        // when a detail summary exists)
        const hasTranscript = !!video.transcript_text;
        const hasDetailSummary = !!video.detail_summary;
        const detailSummaryBtn = hasTranscript
            ? `<button class="btn btn-sm btn-success" onclick="generateDetailSummary(${video.id}, ${hasDetailSummary})">
                   <i class="bi bi-file-earmark-text"></i> ${hasDetailSummary ? 'Regenerate Detail Summary' : 'Generate Detail Summary'}
               </button>`
            : `<button class="btn btn-sm btn-success" disabled title="Get the transcript first">
                   <i class="bi bi-file-earmark-text"></i> Generate Detail Summary
               </button>`;
        const mindMapBtn = hasDetailSummary
            ? `<button id="mindMapBtn" class="btn btn-sm btn-purple" onclick="viewMindMap(${video.id})">
                   <i class="bi bi-diagram-3"></i> View Mind Map
               </button>`
            : '';

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
                    <div class="d-flex justify-content-between align-items-center">
                        <h6 class="mb-1">Description</h6>
                        <div class="d-flex gap-1 content-actions">
                            <button type="button" class="btn btn-sm btn-outline-secondary"
                                    onclick="copyContent('videoDescriptionBlock', 'text')" title="Copy description">
                                <i class="bi bi-clipboard"></i> Copy
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-secondary"
                                    onclick="shareContent('Description — ${escAttr(video.title)}', 'videoDescriptionBlock', 'text')" title="Share description">
                                <i class="bi bi-share"></i> Share
                            </button>
                        </div>
                    </div>
                    <p id="videoDescriptionBlock">${video.description || 'No description available'}</p>
                </div>
            </div>
            ${video.summary_text ? `
            <div class="row mt-3">
                <div class="col-12">
                    <div class="d-flex justify-content-between align-items-center">
                        <h6 class="mb-1">AI Summary</h6>
                        <div class="d-flex gap-1 content-actions">
                            <button type="button" class="btn btn-sm btn-outline-secondary"
                                    onclick="copyContent('aiSummaryBlock', 'text')" title="Copy summary">
                                <i class="bi bi-clipboard"></i> Copy
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-secondary"
                                    onclick="shareContent('AI summary — ${escAttr(video.title)}', 'aiSummaryBlock', 'text')" title="Share summary">
                                <i class="bi bi-share"></i> Share
                            </button>
                        </div>
                    </div>
                    <div class="alert alert-info" id="aiSummaryBlock">
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
            ${video.detail_summary ? `
            <div class="row mt-3">
                <div class="col-12">
                    <div class="d-flex justify-content-between align-items-center">
                        <h6 class="mb-1">Detail Summary</h6>
                        <div class="d-flex gap-1 content-actions">
                            <button type="button" class="btn btn-sm btn-outline-secondary"
                                    onclick="copyContent('detailSummaryBlock', 'text')" title="Copy summary">
                                <i class="bi bi-clipboard"></i> Copy
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-secondary"
                                    onclick="shareContent('Detail summary — ${escAttr(video.title)}', 'detailSummaryBlock', 'text')" title="Share summary">
                                <i class="bi bi-share"></i> Share
                            </button>
                        </div>
                    </div>
                    <div class="alert alert-success detail-summary-block" id="detailSummaryBlock">
                        ${renderMarkdown(video.detail_summary)}
                    </div>
                    <small class="text-muted">
                        Generated: ${video.detail_summary_generated_at ? new Date(video.detail_summary_generated_at).toLocaleString() : 'Unknown'}
                    </small>
                    <!-- Feature 6: mind map rendered inline right below the detail summary -->
                    <div id="mindMapContainer" class="mt-3"></div>
                </div>
            </div>
            ` : ''}
            <div class="row mt-3">
                <div class="col-12">
                    <div class="d-flex flex-wrap gap-2 align-items-center">
                        ${!hasTranscript ? `
                        <button class="btn btn-sm btn-warning" onclick="fetchTranscript(${video.id})">
                            <i class="bi bi-file-text"></i> Get Transcript
                        </button>` : ''}
                        ${detailSummaryBtn}
                        ${mindMapBtn}
                    </div>
                    ${hasTranscript ? '<small class="text-muted d-block mt-1">Transcript downloaded — you can generate a detail summary and a mind map.</small>' : ''}
                </div>
            </div>
            ${video.transcript_text ? `
            <div class="row mt-3">
                <div class="col-12">
                    <div class="d-flex justify-content-between align-items-center">
                        <h6 class="mb-1">Transcript</h6>
                        <div class="d-flex gap-1 content-actions">
                            <button type="button" class="btn btn-sm btn-outline-secondary"
                                    onclick="copyContent('transcriptBlock', 'text')" title="Copy transcript">
                                <i class="bi bi-clipboard"></i> Copy
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-secondary"
                                    onclick="shareContent('Transcript — ${escAttr(video.title)}', 'transcriptBlock', 'text')" title="Share transcript">
                                <i class="bi bi-share"></i> Share
                            </button>
                        </div>
                    </div>
                    <div class="bg-light p-3 rounded" style="max-height: 300px; overflow-y: auto;">
                        <pre id="transcriptBlock" style="white-space: pre-wrap;">${video.transcript_text}</pre>
                    </div>
                </div>
            </div>
            ` : ''}
        `;

        $('#videoDetailsContent').html(content);
        $('#videoDetailsModal').modal('show');
        if (afterRender) afterRender();
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

// Feature 5: generate a well-structured detail summary from the transcript.
function generateDetailSummary(videoId, hasExisting) {
    const msg = hasExisting
        ? 'Regenerate the detail summary? The existing one will be replaced.'
        : 'Generate a detail summary from the video transcript?';
    if (!confirm(msg)) {
        return;
    }

    $.ajax({
        url: `/api/videos/${videoId}/detail-summary${hasExisting ? '?force_regenerate=true' : ''}`,
        method: 'POST',
        success: function(response) {
            alert('Detail summary generated successfully!');
            // Reload the details modal so the new summary and the mind-map
            // button appear immediately.
            viewVideoDetails(videoId);
        },
        error: function(xhr) {
            alert('Failed to generate detail summary: ' + (xhr.responseJSON?.detail || 'Unknown error'));
        }
    });
}

// Feature 6: generate the mind map and render it as an inline SVG vector
// diagram directly below the Detail Summary section (no popup).
function viewMindMap(videoId) {
    const $btn = $('#mindMapBtn');
    const original = $btn.html();
    $btn.prop('disabled', true).html(
        '<span class="spinner-border spinner-border-sm"></span> Generating...'
    );

    $.ajax({
        url: `/api/videos/${videoId}/mindmap`,
        method: 'POST',
        success: function(response) {
            $btn.prop('disabled', false).html(original);
            const container = $('#mindMapContainer');
            if (container.length === 0) {
                // Detail summary section not rendered yet — reopen details.
                viewVideoDetails(videoId, function() {
                    renderMindMapSvg($('#mindMapContainer'), response.mind_map);
                });
            } else {
                renderMindMapSvg(container, response.mind_map);
            }
        },
        error: function(xhr) {
            $btn.prop('disabled', false).html(original);
            alert('Failed to generate mind map: ' + (xhr.responseJSON?.detail || 'Unknown error'));
        }
    });
}

// Parse mind-map markdown into a {content, children} tree.
function parseMindMapTree(text) {
    if (!text) return null;
    const lines = text.split('\n').filter(l => l.trim() !== '');
    let root = null;
    const stack = [];  // stack of {level, node}
    lines.forEach(function(line) {
        const indent = line.match(/^\s*/)[0].length;
        const content = line.trim().replace(/^[-*#]+\s*/, '').replace(/^#+\s*/, '');
        if (!content) return;
        const level = line.startsWith('#') ? 0 : Math.floor(indent / 2);
        const node = { content: content, children: [] };
        if (root === null) {
            root = node;
            stack.push({ level: level, node: node });
        } else {
            while (stack.length > 0 && stack[stack.length - 1].level >= level) {
                stack.pop();
            }
            if (stack.length === 0) {
                root.children.push(node);  // extra top-level branch
            } else {
                stack[stack.length - 1].node.children.push(node);
            }
            stack.push({ level: level, node: node });
        }
    });
    return root;
}

// Minimal markdown renderer for summary blocks (headings, bullets, bold, paragraphs).
function renderMarkdown(text) {
    if (!text) return '';
    let html = '';
    const lines = text.split('\n');
    let inList = false;
    lines.forEach(function(line) {
        const trimmed = line.trim();
        if (trimmed.startsWith('### ')) {
            if (inList) { html += '</ul>'; inList = false; }
            html += `<h6 class="mt-2">${trimmed.slice(4)}</h6>`;
        } else if (trimmed.startsWith('## ')) {
            if (inList) { html += '</ul>'; inList = false; }
            html += `<h5 class="mt-3">${trimmed.slice(3)}</h5>`;
        } else if (trimmed.startsWith('# ')) {
            if (inList) { html += '</ul>'; inList = false; }
            html += `<h4 class="mt-3">${trimmed.slice(2)}</h4>`;
        } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
            if (!inList) { html += '<ul>'; inList = true; }
            html += `<li>${inlineFormat(trimmed.slice(2))}</li>`;
        } else if (trimmed === '') {
            if (inList) { html += '</ul>'; inList = false; }
        } else {
            if (inList) { html += '</ul>'; inList = false; }
            html += `<p class="mb-2">${inlineFormat(trimmed)}</p>`;
        }
    });
    if (inList) html += '</ul>';
    return html;
}

function inlineFormat(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/\*([^*]+)\*/g, '<em>$1</em>');
}

// Render the mind map as a true vector (SVG) diagram: rounded node boxes
// connected by curved bezier links, laid out left→right in a horizontal tree.
function renderMindMapSvg(container, text) {
    const root = parseMindMapTree(text);
    if (!root) {
        container.html('<div class="text-muted">No mind map data.</div>');
        return;
    }

    // Escape helper for SVG text content.
    const esc = function(s) {
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    };

    const NODE_H = 34;         // node height
    const V_GAP = 12;          // vertical gap between sibling subtrees
    const H_GAP = 48;          // horizontal gap between depth levels
    const CHAR_W = 7.2;        // approx px per character at 13px font
    const COLORS = [          // level accent colors (fill, border)
        { fill: '#6f42c1', text: '#fff' },
        { fill: '#0d6efd', text: '#fff' },
        { fill: '#198754', text: '#fff' },
        { fill: '#fd7e14', text: '#000' },
        { fill: '#20c997', text: '#000' },
        { fill: '#6c757d', text: '#fff' }
    ];

    // Measure each node and compute subtree heights bottom-up.
    function measure(node, depth) {
        const isLeaf = !node.children || node.children.length === 0;
        const color = COLORS[Math.min(depth, COLORS.length - 1)];
        node._w = Math.max(90, Math.min(260, node.content.length * CHAR_W + 24));
        node._lines = isLeaf && node.content.length > 34
            ? Math.ceil(node.content.length / 34) : 1;
        if (node._lines > 1) node._h = NODE_H + (node._lines - 1) * 16;
        else node._h = NODE_H;
        node._color = color;

        if (isLeaf) {
            node._subH = node._h;
        } else {
            let sum = 0;
            node.children.forEach(function(c, i) {
                measure(c, depth + 1);
                sum += c._subH;
                if (i < node.children.length - 1) sum += V_GAP;
            });
            node._subH = Math.max(node._h, sum);
        }
    }
    measure(root, 0);

    const totalH = root._subH + 40;
    // Total width: root + deepest chain of levels.
    let maxDepth = 0;
    (function walk(n, d) { maxDepth = Math.max(maxDepth, d); (n.children || []).forEach(c => walk(c, d + 1)); })(root, 0);
    const totalW = 40 + (maxDepth + 1) * 130 + maxDepth * H_GAP + 40;

    const parts = [];
    const svgW = Math.max(container.width() || 800, totalW);
    const startY = (totalH - root._subH) / 2 + 20;
    const startX = 20;

    // Recursive layout + draw.
    function draw(node, x, yTop, ySubCenter, depth) {
        const color = node._color;
        const y = ySubCenter - node._h / 2;
        const isRoot = depth === 0;

        // Curved bezier connector from parent right edge to this node's left edge.
        if (depth > 0) {
            const px = node._px, py = node._py;
            const mx = (px + x) / 2;
            parts.push(`<path d="M ${px} ${py} C ${mx} ${py}, ${mx} ${y + node._h / 2}, ${x} ${y + node._h / 2}"
                fill="none" stroke="${color.fill}" stroke-opacity="0.55" stroke-width="2"/>`);
        }

        // Node box.
        const rx = isRoot ? 18 : 10;
        parts.push(`<rect x="${x}" y="${y}" width="${node._w}" height="${node._h}" rx="${rx}"
            fill="${color.fill}" stroke="${color.fill}" stroke-opacity="0.9"/>`);
        // Text (wrap leaf content if long).
        const lines = [];
        if (node._lines > 1) {
            let remaining = node.content;
            while (remaining.length > 34) {
                let cut = remaining.lastIndexOf(' ', 34);
                if (cut <= 0) cut = 34;
                lines.push(remaining.slice(0, cut));
                remaining = remaining.slice(cut).trim();
            }
            lines.push(remaining);
        } else {
            lines.push(node.content);
        }
        const textX = x + node._w / 2;
        const baseY = y + node._h / 2 - (lines.length - 1) * 8 + 4.5;
        lines.forEach(function(ln, i) {
            parts.push(`<text x="${textX}" y="${baseY + i * 16}" text-anchor="middle"
                fill="${color.text}" font-size="13">${esc(ln)}</text>`);
        });

        // Children.
        if (node.children && node.children.length > 0) {
            const childX = x + node._w + H_GAP;
            // Parent anchor: right edge, vertically centered.
            const anchorY = y + node._h / 2;
            let cy = yTop;
            node.children.forEach(function(c) {
                c._px = x + node._w;
                c._py = anchorY;
                draw(c, childX, cy, cy + c._subH / 2, depth + 1);
                cy += c._subH + V_GAP;
            });
        }
    }
    draw(root, startX, startY, startY + root._subH / 2, 0);

    container.html(`
        <div class="mindmap-svg-wrap">
            <div class="mindmap-svg-toolbar d-flex gap-2 mb-2">
                <button type="button" class="btn btn-sm btn-outline-secondary"
                        onclick="copyContent('mindmap-svg', 'svg')">Copy</button>
                <button type="button" class="btn btn-sm btn-outline-secondary"
                        onclick="shareContent('Mind map', 'mindmap-svg', 'svg')">Share</button>
            </div>
            <div class="mindmap-svg-scroll">
                <svg id="mindmap-svg" xmlns="http://www.w3.org/2000/svg"
                     width="${svgW}" height="${totalH}" viewBox="0 0 ${svgW} ${totalH}"
                     class="mindmap-svg" role="img" aria-label="Mind map">
                    <rect width="100%" height="100%" fill="#ffffff"/>
                    ${parts.join('\n')}
                </svg>
            </div>
        </div>`);
}

// Generic copy / share helpers for text and rendered content blocks.
function copyContent(sourceId, mode) {
    let text = '';
    if (mode === 'svg') {
        const el = document.getElementById(sourceId);
        if (!el) return;
        text = new XMLSerializer().serializeToString(el);
    } else {
        text = $('#' + sourceId).text();
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function() {
            toastMessage('Copied to clipboard');
        }, function() {
            fallbackCopy(text);
        });
    } else {
        fallbackCopy(text);
    }
}

function shareContent(title, sourceId, mode) {
    let text = '';
    if (mode === 'svg') {
        const el = document.getElementById(sourceId);
        if (!el) return;
        text = new XMLSerializer().serializeToString(el);
    } else {
        text = $('#' + sourceId).text();
    }
    if (navigator.share) {
        navigator.share({ title: title, text: text }).catch(function() {});
    } else {
        copyContent(sourceId, mode);
        toastMessage('Sharing not supported here — content copied instead');
    }
}

function fallbackCopy(text) {
    const ta = $('<textarea>').val(text).css({ position: 'fixed', opacity: 0 }).appendTo('body');
    ta[0].select();
    try { document.execCommand('copy'); toastMessage('Copied to clipboard'); }
    catch (e) { alert('Copy failed'); }
    ta.remove();
}

function toastMessage(msg) {
    // Reuse a single toast element.
    if ($('#copyToast').length === 0) {
        $('body').append(`
        <div class="toast align-items-center text-white bg-secondary border-0" id="copyToast"
             role="alert" aria-live="assertive" aria-atomic="true"
             style="position: fixed; bottom: 20px; right: 20px; z-index: 20000;">
            <div class="d-flex">
                <div class="toast-body" id="copyToastBody"></div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto"
                        data-bs-dismiss="toast"></button>
            </div>
        </div>`);
    }
    $('#copyToastBody').text(msg);
    const toastEl = document.getElementById('copyToast');
    if (window.bootstrap && bootstrap.Toast) {
        bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 1800 }).show();
    }
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
            // Refresh the details modal if it is open so the detail-summary
            // button becomes enabled, otherwise just reload the list.
            if ($('#videoDetailsModal').hasClass('show')) {
                viewVideoDetails(videoId);
            } else {
                loadVideos(currentPage);
            }
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

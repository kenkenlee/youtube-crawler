// Channels Management JavaScript

let currentChannelPage = 0;

let channelViewMode = localStorage.getItem('channelViewMode') || 'list';

$(document).ready(function() {
    setChannelViewMode(channelViewMode, true);
    loadChannels();

    // Filter by active only
    $('#showActiveOnly').change(function() {
        currentChannelPage = 0;
        loadChannels();
    });
});

function loadChannels(page = 0) {
    const showActiveOnly = $('#showActiveOnly').is(':checked');
    const limit = 50;
    const skip = page * limit;

    let url = `/api/channels?skip=${skip}&limit=${limit}`;
    if (showActiveOnly) url += '&crawl_enabled=true';

    if (channelViewMode === 'categories') {
        loadChannelsByCategory();
        return;
    }

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

        currentChannelPage = page;
        updateChannelPagination(data.length, limit, page);
    }).fail(function() {
        $('#channelsList').html('<p class="text-danger">Failed to load channels</p>');
    });
}

function updateChannelPagination(itemCount, limit, currentPage) {
    const hasMore = itemCount === limit;
    const hasPrevious = currentPage > 0;

    let paginationHtml = '<nav aria-label="Channel pagination"><ul class="pagination justify-content-center mt-4">';

    // Previous button
    if (hasPrevious) {
        paginationHtml += `<li class="page-item"><a class="page-link" href="#" onclick="loadChannels(${currentPage - 1}); return false;">Previous</a></li>`;
    } else {
        paginationHtml += '<li class="page-item disabled"><span class="page-link">Previous</span></li>';
    }

    // Page numbers
    const startPage = Math.max(0, currentPage - 2);
    const endPage = currentPage + 2;

    for (let i = startPage; i <= endPage; i++) {
        if (i === currentPage) {
            paginationHtml += `<li class="page-item active"><span class="page-link">${i + 1}</span></li>`;
        } else {
            paginationHtml += `<li class="page-item"><a class="page-link" href="#" onclick="loadChannels(${i}); return false;">${i + 1}</a></li>`;
        }
    }

    // Next button
    if (hasMore) {
        paginationHtml += `<li class="page-item"><a class="page-link" href="#" onclick="loadChannels(${currentPage + 1}); return false;">Next</a></li>`;
    } else {
        paginationHtml += '<li class="page-item disabled"><span class="page-link">Next</span></li>';
    }

    paginationHtml += '</ul></nav>';

    // Add or update pagination
    $('#channelPagination').remove();
    $('#channelsList').after(`<div id="channelPagination">${paginationHtml}</div>`);
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
        <div class="channel-card-compact clickable-card"
             onclick="viewChannel(${channel.id})"
             title="Click to view this channel's videos">
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
                                ${(channel.categories || []).map(c => `<span class="badge bg-light text-dark border ms-1">${c.name_zh || c.slug}</span>`).join('') || (channel.category ? `<span class="badge bg-light text-dark border ms-1">${channel.category.name_zh || channel.category.slug}</span>` : '')}
                                <span class="text-muted small ms-2">
                                    <i class="bi bi-play-circle"></i> ${channel.video_count} videos
                                    <span class="text-success">(${channel.summarized_count} summarized)</span>
                                </span>
                            </div>
                        </div>
                        <div class="btn-group btn-group-sm" onclick="event.stopPropagation()">
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
                        <div class="d-flex gap-2" onclick="event.stopPropagation()">
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
    const channelUrl = $('#channelUrl').val().trim();
    const description = $('#channelDescription').val().trim();
    const keywords = $('#channelKeywords').val();
    const crawlFrequency = $('#crawlFrequency').val();
    const crawlEnabled = $('#crawlEnabled').is(':checked');

    // URL is the only required field
    if (!channelUrl) {
        alert('Please enter the YouTube Channel URL');
        return;
    }

    const keywordsList = keywords ? keywords.split(',').map(k => k.trim()).filter(k => k) : [];

    const payload = {
        url: channelUrl,
        description: description || null,
        keywords: keywordsList,
        crawl_enabled: crawlEnabled,
        crawl_frequency: crawlFrequency
    };

    // Show loading state — fetching channel info from YouTube can take a moment
    const originalText = $('#addChannelModal .btn-primary').text();
    $('#addChannelModal .btn-primary').text('Fetching channel info...').prop('disabled', true);

    $.ajax({
        url: '/api/channels/from-url',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(payload),
        timeout: 60000, // recover if the server dies mid-request instead of hanging forever
        success: function(response) {
            $('#addChannelModal .btn-primary').text(originalText).prop('disabled', false);
            alert(`Channel added! Reference ID: ${response.channel_id}, Name: ${response.channel_name}`);
            $('#addChannelModal').modal('hide');
            $('#addChannelForm')[0].reset();
            loadChannels();
        },
        error: function(xhr, textStatus) {
            $('#addChannelModal .btn-primary').text(originalText).prop('disabled', false);

            if (textStatus === 'timeout') {
                alert('The request timed out. The channel may have been added — refresh the page to check.');
                loadChannels();
                return;
            }
            if (xhr.status === 0) {
                alert('Lost connection to the server (it may have restarted). The channel may have been added — refresh the page to check.');
                loadChannels();
                return;
            }

            if (xhr.status === 400 && xhr.responseJSON?.detail?.includes('already exists')) {
                alert('This channel already exists in your database.');
                loadChannels();
            } else if (xhr.status === 400) {
                alert('Could not extract channel ID from URL. Please check the URL format (e.g., https://www.youtube.com/@channelname).');
            } else if (xhr.status === 404) {
                alert('Channel not found on YouTube. Please check the URL.');
            } else {
                alert('Failed to add channel: ' + (xhr.responseJSON?.detail || 'Unknown error'));
            }
        }
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

// Format a number compactly (e.g. 1234567 -> 1.2M) — local copy since
// formatNumber lives in videos.js which isn't loaded on this page.
function formatNumber(num) {
    if (!num && num !== 0) return '';
    if (num >= 1e9) return (num / 1e9).toFixed(1).replace(/\.0$/, '') + 'B';
    if (num >= 1e6) return (num / 1e6).toFixed(1).replace(/\.0$/, '') + 'M';
    if (num >= 1e3) return (num / 1e3).toFixed(1).replace(/\.0$/, '') + 'K';
    return String(num);
}

// ---------- Feature 11: search YouTube channels by keyword ----------
function searchYouTubeChannels() {
    const query = $('#channelSearchQuery').val().trim();
    if (query.length < 2) {
        alert('Please enter at least 2 characters to search.');
        return;
    }

    const $results = $('#channelSearchResults');
    $results.html('<p class="text-muted"><span class="spinner-border spinner-border-sm me-1"></span>Searching YouTube...</p>');

    $.ajax({
        url: '/api/channels/search/youtube?q=' + encodeURIComponent(query),
        method: 'GET',
        timeout: 30000,
        success: function(results) {
            if (!results || results.length === 0) {
                $results.html('<div class="alert alert-warning mb-0">No channels found for this search. Try different keywords.</div>');
                return;
            }
            let html = `<p class="text-muted mb-2">${results.length} channels found — click <strong>Select</strong> to fill the form:</p>
                <div class="list-group channel-search-list">`;
            results.forEach(function(ch) {
                const addedBadge = ch.already_added
                    ? '<span class="badge bg-secondary ms-2">Already added</span>'
                    : '<span class="badge bg-success ms-2">New</span>';
                html += `
                <div class="list-group-item d-flex align-items-center gap-3">
                    <img src="${ch.thumbnail}" alt="" class="rounded-circle" style="width:48px;height:48px;object-fit:cover;" onerror="this.style.display='none'">
                    <div class="flex-grow-1">
                        <div><strong>${ch.channel_name}</strong>${addedBadge}</div>
                        <div class="small text-muted">${ch.subscriber_count.toLocaleString()} subscribers · ${ch.video_count.toLocaleString()} videos</div>
                        <div class="small text-muted text-truncate" style="max-width:420px;">${ch.description || ''}</div>
                    </div>
                    <button type="button" class="btn btn-sm ${ch.already_added ? 'btn-outline-secondary' : 'btn-outline-primary'}"
                            onclick="selectSearchResult('${escAttr(ch.channel_url)}')"
                            ${ch.already_added ? 'disabled' : ''}>
                        ${ch.already_added ? 'Added' : 'Select'}
                    </button>
                </div>`;
            });
            html += '</div>';
            $results.html(html);
        },
        error: function(xhr) {
            $results.html('<div class="alert alert-danger mb-0">Search failed: ' + (xhr.responseJSON?.detail || xhr.statusText) + '</div>');
        }
    });
}

function selectSearchResult(channelUrl) {
    // Fill the URL field — the backend resolves the rest from YouTube
    $('#channelUrl').val(channelUrl);
    $('#channelDescription').val('');
    // Scroll to the form so the user can confirm and click Add Channel
    $('#channelUrl')[0].scrollIntoView({ behavior: 'smooth', block: 'center' });
    $('#channelUrl').trigger('focus');
    // Highlight that the form has been filled from the search result
    $('#channelUrl').addClass('border-success');
    setTimeout(function() { $('#channelUrl').removeClass('border-success'); }, 2500);
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

function viewChannel(channelId) {
    window.location.href = `/videos?channel_id=${channelId}`;
}

function editChannel(channelId) {
    $.when($.get(`/api/channels/${channelId}`), $.get('/api/categories/')).done(function(chRes, catRes) {
        const channel = chRes[0];
        const cats = catRes[0] || [];
        $('#editChannelId').val(channel.id);
        $('#editChannelName').val(channel.channel_name);
        $('#editChannelDescription').val(channel.description || '');
        $('#editChannelKeywords').val(channel.keywords ? channel.keywords.join(', ') : '');
        $('#editCrawlFrequency').val(channel.crawl_frequency);
        $('#editCrawlEnabled').prop('checked', channel.crawl_enabled);
        const selected = new Set((channel.categories || []).map(function(c) { return c.id; }));
        if (channel.category_id) selected.add(channel.category_id);
        const $sel = $('#editChannelCategories').empty();
        cats.forEach(function(c) {
            $sel.append($('<option>').val(c.id).text((c.name_zh || c.slug) + ' / ' + (c.name_en || '')).prop('selected', selected.has(c.id)));
        });
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

    const categoryIds = ($('#editChannelCategories').val() || []).map(String);
    const payload = {
        channel_name: channelName,
        description: description,
        keywords: keywordsList,
        crawl_enabled: crawlEnabled,
        crawl_frequency: crawlFrequency,
        category_ids: categoryIds
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

// ---------- Video search in the Add Single Video modal ----------
// Max 10 results per page; pagination via YouTube's nextPageToken.
let videoSearchState = {
    query: null,
    pageToken: null,       // token for the NEXT page
    prevTokens: [],        // stack of tokens for going back
    pageInfo: null,
    videos: []
};

function searchYouTubeVideos(pageToken = null, direction = 0) {
    const query = $('#videoSearchQuery').val().trim();
    if (!query || query.length < 2) {
        alert('Please enter at least 2 characters to search.');
        return;
    }
    if (direction === 0) {
        // Fresh search — reset state
        videoSearchState = { query: query, pageToken: null, prevTokens: [], pageInfo: null, videos: [] };
    }

    const $btn = $('#videoSearchResults');
    const loadingHtml = '<div class="text-center py-3"><div class="spinner-border spinner-border-sm text-primary"></div> Searching...</div>';
    $btn.removeClass('d-none').html(loadingHtml);

    let url = `/api/videos/search/youtube?q=${encodeURIComponent(query)}`;
    if (pageToken) url += `&page_token=${encodeURIComponent(pageToken)}`;

    $.ajax({
        url: url,
        method: 'GET',
        timeout: 20000,
        success: function(response) {
            videoSearchState.videos = response.videos || [];
            videoSearchState.pageInfo = response.total;

            // Track tokens for prev/next navigation
            if (direction === 0) {
                videoSearchState.prevTokens = [];
            } else if (direction === 1 && videoSearchState.pageToken) {
                videoSearchState.prevTokens.push(videoSearchState.pageToken);
            }
            videoSearchState.pageToken = response.next_page_token;

            renderVideoSearchResults();
        },
        error: function(xhr) {
            const detail = (xhr.responseJSON && xhr.responseJSON.detail) || 'Search failed. Please try again.';
            $btn.html(`<div class="alert alert-danger mb-0">${escAttr(detail)}</div>`);
        }
    });
}

function videoSearchPage(direction) {
    // direction: 1 = next, -1 = prev
    if (direction === 1) {
        if (!videoSearchState.pageToken) return;
        searchYouTubeVideos(videoSearchState.pageToken, 1);
    } else {
        if (videoSearchState.prevTokens.length === 0) return;
        const prevToken = videoSearchState.prevTokens.pop();
        searchYouTubeVideos(prevToken, -1);
    }
}

function renderVideoSearchResults() {
    const $list = $('#videoSearchResults');
    const $pag = $('#videoSearchPagination');
    const videos = videoSearchState.videos;

    if (!videos.length) {
        $list.html('<div class="alert alert-warning mb-0">No videos found for this query.</div>');
        $pag.addClass('d-none');
        return;
    }

    const items = videos.map(v => {
        const views = v.view_count ? formatNumber(v.view_count) + ' views' : '';
        const addedBadge = v.already_added
            ? '<span class="badge bg-secondary ms-1">Already added</span>' : '';
        const btn = v.already_added
            ? ''
            : `<button type="button" class="btn btn-sm btn-outline-success"
                       onclick="selectVideoSearchResult('${v.video_id}')">Select</button>`;
        return `
            <div class="list-group-item">
                <div class="d-flex">
                    <img src="${escAttr(v.thumbnail)}" class="video-search-thumb me-2" alt="">
                    <div class="flex-grow-1 min-w-0">
                        <div class="video-search-title">${escAttr(v.title)} ${addedBadge}</div>
                        <small class="text-muted d-block">${escAttr(v.channel_title)} · ${views} · ${escAttr(v.duration)}</small>
                        <small class="text-muted d-block text-truncate">${escAttr(v.description)}</small>
                    </div>
                    <div class="ms-2">${btn}</div>
                </div>
            </div>`;
    }).join('');

    $list.html(`<div class="list-group">${items}</div>`);

    // Pagination controls
    const pageNum = videoSearchState.prevTokens.length + 1;
    $pag.removeClass('d-none');
    $('#videoSearchPageInfo').text(`Page ${pageNum} · up to 10 results`);
    $('#videoSearchPrevBtn').prop('disabled', videoSearchState.prevTokens.length === 0);
    $('#videoSearchNextBtn').prop('disabled', !videoSearchState.pageToken);
}

function selectVideoSearchResult(videoId) {
    $('#videoUrl').val(`https://www.youtube.com/watch?v=${videoId}`);
    $('#videoUrl').addClass('border-success');
    setTimeout(function() { $('#videoUrl').removeClass('border-success'); }, 2500);
    // Keep results visible so the user can compare or pick another video
}

function addVideo() {
    const videoUrl = $('#videoUrl').val().trim();
    const autoSummarize = $('#autoSummarize').is(':checked');

    // Validate required fields
    if (!videoUrl) {
        alert('Please enter a YouTube video URL');
        return;
    }

    // Extract video ID from URL
    const videoId = extractVideoId(videoUrl);
    if (!videoId) {
        alert('Invalid YouTube URL. Please enter a valid YouTube video URL.');
        return;
    }

    // Show loading state
    const $button = $('#addVideoModal .btn-success');
    const originalText = $button.html();
    $button.html('<span class="spinner-border spinner-border-sm me-2"></span>Adding video...').prop('disabled', true);

    // Add video via API — channel is resolved automatically from YouTube
    $.ajax({
        url: '/api/videos/add-single',
        method: 'POST',
        contentType: 'application/json',
        timeout: 60000,
        data: JSON.stringify({
            video_url: videoUrl,
            video_id: videoId,
            auto_summarize: autoSummarize
        }),
        success: function(response) {
            const channelNote = response.channel_created
                ? ` Its channel "${response.channel_name}" was added automatically and is available for future sessions.`
                : '';
            alert(`Video added successfully!${channelNote}`);
            $('#addVideoModal').modal('hide');
            $('#addVideoForm')[0].reset();
            $button.html(originalText).prop('disabled', false);
            loadChannels(); // Refresh to show updated video count and any newly added channel
        },
        error: function(xhr, textStatus) {
            $button.html(originalText).prop('disabled', false);
            if (textStatus === 'timeout') {
                alert('The request timed out. The video may have been added — refresh the page to check.');
                loadChannels();
            } else if (xhr.status === 400 && xhr.responseJSON?.detail?.includes('already exists')) {
                alert('This video already exists in the database.');
            } else {
                alert('Failed to add video: ' + (xhr.responseJSON?.detail || 'Unknown error'));
            }
        }
    });
}

function extractVideoId(url) {
    // Try multiple URL formats

    // Format 1: https://www.youtube.com/watch?v=VIDEO_ID
    let match = url.match(/[?&]v=([^&]+)/);
    if (match) return match[1];

    // Format 2: https://youtu.be/VIDEO_ID
    match = url.match(/youtu\.be\/([^?]+)/);
    if (match) return match[1];

    // Format 3: https://www.youtube.com/embed/VIDEO_ID
    match = url.match(/youtube\.com\/embed\/([^?]+)/);
    if (match) return match[1];

    // Format 4: Just the video ID
    match = url.match(/^([a-zA-Z0-9_-]{11})$/);
    if (match) return match[1];

    return null;
}


// ---------- Categories view (frontpage) ----------
function setChannelViewMode(mode, skipLoad) {
    channelViewMode = mode === 'categories' ? 'categories' : 'list';
    localStorage.setItem('channelViewMode', channelViewMode);
    $('#viewListBtn').toggleClass('active', channelViewMode === 'list');
    $('#viewCategoriesBtn').toggleClass('active', channelViewMode === 'categories');
    if (!skipLoad) {
        currentChannelPage = 0;
        loadChannels();
    }
}

function loadChannelsByCategory() {
    const showActiveOnly = $('#showActiveOnly').is(':checked');
    $('#channelPagination').remove();
    const container = $('#channelsList');
    container.html('<p class="text-muted">Loading categories…</p>');

    $.when(
        $.get('/api/categories/'),
        $.get('/api/channels/?skip=0&limit=500' + (showActiveOnly ? '&crawl_enabled=true' : ''))
    ).done(function(catRes, chRes) {
        const cats = catRes[0] || [];
        const channels = chRes[0] || [];
        const byCat = {};
        channels.forEach(function(ch) {
            const list = (ch.categories && ch.categories.length) ? ch.categories : (ch.category ? [ch.category] : []);
            if (!list.length) {
                (byCat.__none__ = byCat.__none__ || []).push(ch);
                return;
            }
            list.forEach(function(c) {
                (byCat[c.id] = byCat[c.id] || []).push(ch);
            });
        });

        if (!cats.length && !channels.length) {
            container.html('<p class="text-muted">No channels found.</p>');
            return;
        }

        let html = '<div class="accordion" id="channelCategoryAccordion">';
        cats.forEach(function(cat, idx) {
            const members = byCat[cat.id] || [];
            const collapseId = 'catCollapse' + cat.id;
            html += `
            <div class="accordion-item">
              <h2 class="accordion-header">
                <button class="accordion-button ${idx === 0 ? '' : 'collapsed'}" type="button" data-bs-toggle="collapse" data-bs-target="#${collapseId}">
                  <strong class="me-2">${cat.name_zh || cat.slug}</strong>
                  <span class="text-muted small me-2">${cat.name_en || ''}</span>
                  <span class="badge bg-secondary">${members.length}</span>
                </button>
              </h2>
              <div id="${collapseId}" class="accordion-collapse collapse ${idx === 0 ? 'show' : ''}" data-bs-parent="#channelCategoryAccordion">
                <div class="accordion-body">
                  ${members.length ? members.map(createChannelCard).join('') : '<p class="text-muted mb-0">No channels in this category.</p>'}
                </div>
              </div>
            </div>`;
        });
        const uncat = byCat.__none__ || [];
        if (uncat.length) {
            html += `
            <div class="accordion-item">
              <h2 class="accordion-header">
                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#catCollapseNone">
                  <strong class="me-2">Uncategorized</strong>
                  <span class="badge bg-warning text-dark">${uncat.length}</span>
                </button>
              </h2>
              <div id="catCollapseNone" class="accordion-collapse collapse" data-bs-parent="#channelCategoryAccordion">
                <div class="accordion-body">${uncat.map(createChannelCard).join('')}</div>
              </div>
            </div>`;
        }
        html += '</div>';
        container.html(html);
    }).fail(function() {
        container.html('<p class="text-danger">Failed to load categories view</p>');
    });
}

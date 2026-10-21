// Sessions Management JavaScript

let activeWebSockets = {};
let sessionChannelsData = [];  // cached channel list for sorting / auto-naming

$(document).ready(function() {
    loadSessions();
    loadChannelsForSession();
    loadRecurringSessions();

    // Filter change
    $('#statusFilter').change(function() {
        loadSessions();
    });

    // Channel list sorting (feature 8.1)
    $('#channelSort').change(function() {
        renderChannelOptions();
    });

    // Recurrence toggle (feature 10)
    $('#recurringToggle').change(function() {
        $('#recurrenceOptions').toggle(this.checked);
    });
    // Auto-refresh every 10 seconds
    setInterval(loadSessions, 10000);
    setInterval(loadRecurringSessions, 10000);
});

// Active recurring sessions panel (feature 11)
function loadRecurringSessions() {
    $.get('/api/sessions', function(data) {
        // Recurring templates: sessions with an interval set that aren't child runs
        const recurring = data.filter(s => s.recurrence_hours && !s.parent_session_id);
        const container = $('#recurringSessionsList');
        if (!container.length) return;
        container.empty();

        if (recurring.length === 0) {
            container.html('<p class="text-muted">No recurring sessions configured</p>');
            return;
        }

        recurring.forEach(function(session) {
            container.append(createRecurringCard(session));
        });
    }).fail(function() {
        const container = $('#recurringSessionsList');
        if (container.length) container.html('<p class="text-danger">Failed to load recurring sessions</p>');
    });
}

function createRecurringCard(session) {
    const activeBadge = session.recurrence_active
        ? '<span class="badge bg-success"><i class="bi bi-check-circle"></i> Active</span>'
        : '<span class="badge bg-secondary"><i class="bi bi-pause-circle"></i> Paused</span>';

    const lastRun = session.completed_at || session.started_at
        ? new Date(session.completed_at || session.started_at).toLocaleString()
        : 'Never';

    // Next run = last run + interval (only meaningful while active)
    let nextRun = '-';
    if (session.recurrence_active) {
        const base = session.completed_at || session.started_at || session.created_at;
        if (base) {
            nextRun = new Date(new Date(base).getTime() + session.recurrence_hours * 3600 * 1000).toLocaleString();
        }
    }

    const toggleButton = session.recurrence_active
        ? `<button class="btn btn-sm btn-outline-secondary" onclick="pauseRecurrence(${session.id}); loadRecurringSessions();">
               <i class="bi bi-pause-circle"></i> Pause
           </button>`
        : `<button class="btn btn-sm btn-outline-success" onclick="resumeRecurrence(${session.id}); loadRecurringSessions();">
               <i class="bi bi-play-circle"></i> Resume
           </button>`;

    return `
        <div class="card mb-2 ${session.recurrence_active ? 'border-success' : 'border-secondary'}" id="recurring-${session.id}">
            <div class="card-body py-2">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <strong>${session.session_name}</strong>
                        ${activeBadge}
                        <span class="badge ${session.status === 'running' ? 'bg-warning text-dark' : 'bg-light text-dark'}">
                            ${session.status === 'running' ? '<i class="bi bi-arrow-repeat"></i> Running now' : session.status}
                        </span>
                    </div>
                    <div class="btn-group">
                        <button class="btn btn-sm btn-outline-primary" onclick="viewSessionDetails(${session.id})">
                            <i class="bi bi-eye"></i> Details
                        </button>
                        ${toggleButton}
                    </div>
                </div>
                <div class="row mt-1">
                    <div class="col-md-3">
                        <small class="text-muted"><i class="bi bi-arrow-repeat"></i> Every ${session.recurrence_hours}h</small>
                    </div>
                    <div class="col-md-3">
                        <small class="text-muted"><i class="bi bi-clock-history"></i> Last run: ${lastRun}</small>
                    </div>
                    <div class="col-md-3">
                        <small class="text-muted"><i class="bi bi-clock"></i> Next run: ${nextRun}</small>
                    </div>
                    <div class="col-md-3">
                        <small class="text-muted"><i class="bi bi-collection-play"></i> ${session.total_videos_found} videos found</small>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function loadSessions() {
    const status = $('#statusFilter').val();
    const url = status ? `/api/sessions?status=${status}` : '/api/sessions';

    $.get(url, function(data) {
        const container = $('#sessionsList');
        container.empty();

        if (data.length === 0) {
            container.html('<p class="text-muted">No sessions found</p>');
            return;
        }

        data.forEach(function(session) {
            const sessionCard = createSessionCard(session);
            container.append(sessionCard);

            // Connect WebSocket for running sessions
            if (session.status === 'running') {
                connectWebSocket(session.id);
            }
        });
    }).fail(function() {
        $('#sessionsList').html('<p class="text-danger">Failed to load sessions</p>');
    });
}

function createSessionCard(session) {
    const statusClass = getStatusClass(session.status);
    const statusBadge = `<span class="badge ${statusClass}">${session.status.toUpperCase()}</span>`;

    const progress = session.total_channels > 0
        ? Math.round((session.processed_channels / session.total_channels) * 100)
        : 0;

    const startedAt = session.started_at
        ? new Date(session.started_at).toLocaleString()
        : 'Not started';

    const completedAt = session.completed_at
        ? new Date(session.completed_at).toLocaleString()
        : '-';

    const keywords = session.filter_keywords && session.filter_keywords.length > 0
        ? session.filter_keywords.map(k => `<span class="badge bg-info me-1">${k}</span>`).join('')
        : '<span class="text-muted">No filters</span>';

    const recurrenceBadge = session.recurrence_hours
        ? `<span class="badge ${session.recurrence_active ? 'bg-primary' : 'bg-secondary'}">
               <i class="bi bi-arrow-repeat"></i> Every ${session.recurrence_hours}h${session.recurrence_active ? '' : ' (paused)'}
           </span>`
        : '';

    const recurrenceButton = session.recurrence_hours
        ? (session.recurrence_active
            ? `<button class="btn btn-sm btn-outline-secondary" onclick="pauseRecurrence(${session.id})">
                   <i class="bi bi-pause-circle"></i> Pause Recurrence
               </button>`
            : `<button class="btn btn-sm btn-outline-success" onclick="resumeRecurrence(${session.id})">
                   <i class="bi bi-play-circle"></i> Resume Recurrence
               </button>`)
        : '';

    const cancelButton = session.status === 'running'
        ? `<button class="btn btn-sm btn-warning" onclick="cancelSession(${session.id})">
               <i class="bi bi-stop-circle"></i> Cancel
           </button>`
        : '';

    return `
        <div class="card mb-3" id="session-${session.id}">
            <div class="card-header">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <h5 class="mb-0">${session.session_name}</h5>
                        <small class="text-muted">${session.session_type}</small>
                    </div>
                    <div>
                        ${recurrenceBadge}
                        ${statusBadge}
                    </div>
                </div>
            </div>
            <div class="card-body">
                <div class="row mb-3">
                    <div class="col-md-3">
                        <strong>Channels:</strong> ${session.processed_channels}/${session.total_channels}
                    </div>
                    <div class="col-md-3">
                        <strong>Videos Found:</strong> ${session.total_videos_found}
                    </div>
                    <div class="col-md-3">
                        <strong>Videos Processed:</strong> ${session.videos_processed}
                    </div>
                    <div class="col-md-3">
                        <strong>Summarized:</strong> ${session.videos_summarized}
                    </div>
                </div>

                <div class="mb-2">
                    <small class="text-muted"><i class="bi bi-collection-play"></i> Videos per channel: ${session.max_videos ?? 5}</small>
                </div>

                ${session.status === 'running' || session.status === 'completed' ? `
                <div class="mb-3">
                    <div class="d-flex justify-content-between mb-1">
                        <span>Progress</span>
                        <span>${progress}%</span>
                    </div>
                    <div class="progress">
                        <div class="progress-bar progress-bar-striped ${session.status === 'running' ? 'progress-bar-animated' : ''}"
                             role="progressbar"
                             style="width: ${progress}%"
                             id="progress-${session.id}">
                        </div>
                    </div>
                </div>
                ` : ''}

                <div class="row mb-2">
                    <div class="col-md-6">
                        <small class="text-muted"><strong>Started:</strong> ${startedAt}</small>
                    </div>
                    <div class="col-md-6">
                        <small class="text-muted"><strong>Completed:</strong> ${completedAt}</small>
                    </div>
                </div>

                <div class="mb-2">
                    <strong>Keywords:</strong> ${keywords}
                </div>

                ${session.error_count > 0 ? `
                <div class="alert alert-warning mb-2">
                    <i class="bi bi-exclamation-triangle"></i> ${session.error_count} error(s) occurred
                </div>
                ` : ''}

                <div class="btn-group">
                    <button class="btn btn-sm btn-primary" onclick="viewSessionDetails(${session.id})">
                        <i class="bi bi-eye"></i> View Details
                    </button>
                    <button class="btn btn-sm btn-info" onclick="viewSessionVideos(${session.id})">
                        <i class="bi bi-collection-play"></i> View Videos
                    </button>
                    ${recurrenceButton}
                    ${cancelButton}
                    <button class="btn btn-sm btn-danger" onclick="deleteSession(${session.id})">
                        <i class="bi bi-trash"></i> Delete
                    </button>
                </div>
            </div>
        </div>
    `;
}

// Show/hide the custom hours input depending on the preset dropdown (feature 10)
function toggleRecurrenceCustom() {
    $('#recurrenceCustomWrap').toggle($('#recurrencePreset').val() === 'custom');
}

function loadChannelsForSession() {
    $.get('/api/channels?limit=100', function(data) {
        sessionChannelsData = data;
        renderChannelOptions();
    });
}

// Render channel options in the current sort order (feature 8.1)
function renderChannelOptions() {
    const select = $('#sessionChannels');
    const sortMode = $('#channelSort').val() || 'name';
    const channels = [...sessionChannelsData];

    if (sortMode === 'added') {
        // Date added = when the channel record was created (newest first)
        channels.sort(function(a, b) {
            return new Date(b.created_at || 0) - new Date(a.created_at || 0);
        });
    } else {
        // Default: alphabetical by channel name
        channels.sort(function(a, b) {
            return (a.channel_name || '').localeCompare(b.channel_name || '');
        });
    }

    select.empty();
    channels.forEach(function(channel) {
        const enabled = channel.crawl_enabled ? '' : ' (disabled)';
        select.append(`<option value="${channel.id}">${channel.channel_name}${enabled}</option>`);
    });
}

function createSession() {
    let sessionName = $('#sessionName').val();
    const sessionType = $('#sessionType').val();
    const selectedChannels = $('#sessionChannels').val();
    const keywords = $('#sessionKeywords').val();
    const maxVideos = parseInt($('#maxVideos').val()) || 5;

    if (!selectedChannels || selectedChannels.length === 0) {
        alert('Please select at least one channel');
        return;
    }

    if (maxVideos < 1 || maxVideos > 200) {
        alert('Number of videos per channel must be between 1 and 200');
        return;
    }

    // Recurrence (feature 10) — preset dropdown, or the custom input when "Custom..." is selected
    let recurrenceHours = null;
    if ($('#recurringToggle').is(':checked')) {
        const preset = $('#recurrencePreset').val();
        if (preset === 'custom') {
            recurrenceHours = parseInt($('#recurrenceHours').val());
        } else {
            recurrenceHours = parseInt(preset);
        }
        if (isNaN(recurrenceHours) || recurrenceHours < 1 || recurrenceHours > 720) {
            alert('Recurrence interval must be between 1 and 720 hours');
            return;
        }
    }

    const keywordsList = keywords ? keywords.split(',').map(k => k.trim()).filter(k => k) : [];

    // Feature 9: auto-generate the session name when none was provided —
    // selected channel names + filter keywords + date + time.
    if (!sessionName || sessionName.trim() === '') {
        const channelNames = selectedChannels.map(function(id) {
            const ch = sessionChannelsData.find(c => String(c.id) === String(id));
            return ch ? ch.channel_name : `Channel ${id}`;
        });
        const now = new Date();
        const dateStr = now.getFullYear() + '-' +
            String(now.getMonth() + 1).padStart(2, '0') + '-' +
            String(now.getDate()).padStart(2, '0');
        const timeStr = String(now.getHours()).padStart(2, '0') + ':' +
            String(now.getMinutes()).padStart(2, '0');
        const parts = [channelNames.join(', ')];
        if (keywordsList.length > 0) {
            parts.push('[' + keywordsList.join(', ') + ']');
        }
        parts.push(dateStr, timeStr);
        sessionName = parts.join(' - ');
    }

    const payload = {
        session_name: sessionName,
        session_type: sessionType,
        channel_ids: selectedChannels.map(id => parseInt(id)),
        filter_keywords: keywordsList,
        max_videos: maxVideos,
        recurrence_hours: recurrenceHours
    };

    $.ajax({
        url: '/api/sessions',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(payload),
        success: function(response) {
            alert('Session created successfully!');
            $('#newSessionModal').modal('hide');
            $('#newSessionForm')[0].reset();
            loadSessions();
        },
        error: function(xhr) {
            alert('Failed to create session: ' + (xhr.responseJSON?.detail || 'Unknown error'));
        }
    });
}

function viewSessionDetails(sessionId) {
    $.get(`/api/sessions/${sessionId}`, function(session) {
        $('#sessionDetailsTitle').text(session.session_name);

        const content = `
            <div class="row">
                <div class="col-md-6">
                    <h6>Session Information</h6>
                    <table class="table table-sm">
                        <tr><td><strong>ID:</strong></td><td>${session.id}</td></tr>
                        <tr><td><strong>Type:</strong></td><td>${session.session_type}</td></tr>
                        <tr><td><strong>Status:</strong></td><td><span class="badge ${getStatusClass(session.status)}">${session.status}</span></td></tr>
                        <tr><td><strong>Created:</strong></td><td>${new Date(session.created_at).toLocaleString()}</td></tr>
                        <tr><td><strong>Started:</strong></td><td>${session.started_at ? new Date(session.started_at).toLocaleString() : 'Not started'}</td></tr>
                        <tr><td><strong>Completed:</strong></td><td>${session.completed_at ? new Date(session.completed_at).toLocaleString() : '-'}</td></tr>
                    </table>
                </div>
                <div class="col-md-6">
                    <h6>Statistics</h6>
                    <table class="table table-sm">
                        <tr><td><strong>Total Channels:</strong></td><td>${session.total_channels}</td></tr>
                        <tr><td><strong>Processed Channels:</strong></td><td>${session.processed_channels}</td></tr>
                        <tr><td><strong>Videos Found:</strong></td><td>${session.total_videos_found}</td></tr>
                        <tr><td><strong>Videos Processed:</strong></td><td>${session.videos_processed}</td></tr>
                        <tr><td><strong>Videos Summarized:</strong></td><td>${session.videos_summarized}</td></tr>
                        <tr><td><strong>Errors:</strong></td><td>${session.error_count}</td></tr>
                    </table>
                </div>
            </div>
            ${session.error_log ? `
            <div class="mt-3">
                <h6>Error Log</h6>
                <pre class="bg-light p-3 rounded">${session.error_log}</pre>
            </div>
            ` : ''}
        `;

        $('#sessionDetailsContent').html(content);
        $('#sessionDetailsModal').modal('show');
    }).fail(function() {
        alert('Failed to load session details');
    });
}

function viewSessionVideos(sessionId) {
    window.location.href = `/videos?session_id=${sessionId}`;
}

function pauseRecurrence(sessionId) {
    if (!confirm('Pause recurrence for this session? Future automatic runs will be cancelled (history is kept).')) return;
    $.ajax({
        url: `/api/sessions/${sessionId}/recurrence/pause`,
        type: 'PUT',
        success: function() {
            loadSessions();
        },
        error: function(xhr) {
            alert('Error pausing recurrence: ' + (xhr.responseJSON?.detail || xhr.statusText));
        }
    });
}

function resumeRecurrence(sessionId) {
    $.ajax({
        url: `/api/sessions/${sessionId}/recurrence/resume`,
        type: 'PUT',
        success: function() {
            loadSessions();
        },
        error: function(xhr) {
            alert('Error resuming recurrence: ' + (xhr.responseJSON?.detail || xhr.statusText));
        }
    });
}

function cancelSession(sessionId) {
    if (!confirm('Are you sure you want to cancel this session?')) {
        return;
    }

    $.ajax({
        url: `/api/sessions/${sessionId}/cancel`,
        method: 'PUT',
        success: function() {
            alert('Session cancelled successfully');
            loadSessions();
        },
        error: function(xhr) {
            alert('Failed to cancel session: ' + (xhr.responseJSON?.detail || 'Unknown error'));
        }
    });
}

function deleteSession(sessionId) {
    if (!confirm('Are you sure you want to delete this session?')) {
        return;
    }

    $.ajax({
        url: `/api/sessions/${sessionId}`,
        method: 'DELETE',
        success: function() {
            alert('Session deleted successfully');
            loadSessions();
        },
        error: function(xhr) {
            alert('Failed to delete session: ' + (xhr.responseJSON?.detail || 'Unknown error'));
        }
    });
}

function connectWebSocket(sessionId) {
    if (activeWebSockets[sessionId]) {
        return; // Already connected
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/sessions/${sessionId}`;

    const ws = new WebSocket(wsUrl);

    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        updateSessionProgress(sessionId, data);
    };

    ws.onerror = function(error) {
        console.error('WebSocket error:', error);
    };

    ws.onclose = function() {
        delete activeWebSockets[sessionId];
    };

    activeWebSockets[sessionId] = ws;
}

function updateSessionProgress(sessionId, data) {
    const progressBar = $(`#progress-${sessionId}`);
    if (progressBar.length) {
        progressBar.css('width', data.progress_percentage + '%');
        progressBar.text(Math.round(data.progress_percentage) + '%');
    }
}

function getStatusClass(status) {
    const statusClasses = {
        'completed': 'bg-success',
        'running': 'bg-info',
        'failed': 'bg-danger',
        'pending': 'bg-warning',
        'cancelled': 'bg-secondary'
    };
    return statusClasses[status] || 'bg-secondary';
}

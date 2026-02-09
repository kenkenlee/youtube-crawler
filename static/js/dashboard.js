// Dashboard JavaScript

let dailyChart = null;
let autoRefreshInterval = null;
let dashboardFilters = {
    dateRange: 'week',
    status: 'all',
    keywords: ''
};

// Load dashboard on page load
$(document).ready(function() {
    loadDashboardStats();
    loadRecentActivity();
    loadTopChannels();
    loadDailyChart();
    loadChannelsForCrawl();

    // Initialize features
    setupKeyboardShortcuts();
    initializeTooltips();
    initializeDarkMode();
    initializeAutoRefresh();
    initializeFilters();
    updateLastUpdatedTime();

    // Auto-refresh every 30 seconds (if enabled)
    startAutoRefresh();
});

// Keyboard shortcuts
function setupKeyboardShortcuts() {
    $(document).keydown(function(e) {
        // Alt+C: Go to Channels
        if (e.altKey && e.key === 'c') {
            e.preventDefault();
            window.location.href = '/channels';
        }
        // Alt+V: Go to Videos
        if (e.altKey && e.key === 'v') {
            e.preventDefault();
            window.location.href = '/videos';
        }
        // Alt+S: Go to Sessions
        if (e.altKey && e.key === 's') {
            e.preventDefault();
            window.location.href = '/sessions';
        }
        // Alt+R: Refresh Dashboard
        if (e.altKey && e.key === 'r') {
            e.preventDefault();
            refreshDashboard();
        }
        // Alt+N: New Crawl
        if (e.altKey && e.key === 'n') {
            e.preventDefault();
            $('#newCrawlModal').modal('show');
        }
    });
}

// Initialize tooltips
function initializeTooltips() {
    // Add tooltips to statistics cards
    $('.clickable-card').attr('title', 'Click to view details');

    // Enable Bootstrap tooltips if available
    if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
        var tooltipTriggerList = [].slice.call(document.querySelectorAll('[title]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
}

function loadDashboardStats() {
    $.get('/api/dashboard/stats', function(data) {
        // Animate numbers
        animateNumber('#total-channels', data.total_channels);
        animateNumber('#total-videos', data.total_videos);
        animateNumber('#active-sessions', data.active_sessions);
        animateNumber('#completed-sessions', data.completed_sessions);

        $('#active-channels').text(data.active_channels + ' active');
        $('#summarized-videos').text(data.summarized_videos + ' summarized');
        $('#failed-sessions').text(data.failed_sessions + ' failed');

        // Add click-to-copy functionality
        addCopyFunctionality('#total-channels', data.total_channels);
        addCopyFunctionality('#total-videos', data.total_videos);
        addCopyFunctionality('#active-sessions', data.active_sessions);
        addCopyFunctionality('#completed-sessions', data.completed_sessions);
    }).fail(function() {
        console.error('Failed to load dashboard stats');
    });
}

// Animate numbers counting up
function animateNumber(selector, targetValue) {
    const element = $(selector);
    const currentValue = parseInt(element.text()) || 0;
    const duration = 1000; // 1 second
    const steps = 30;
    const increment = (targetValue - currentValue) / steps;
    let current = currentValue;
    let step = 0;

    const timer = setInterval(function() {
        step++;
        current += increment;

        if (step >= steps) {
            element.text(targetValue);
            clearInterval(timer);
        } else {
            element.text(Math.round(current));
        }
    }, duration / steps);
}

// Add click-to-copy functionality
function addCopyFunctionality(selector, value) {
    $(selector).css('cursor', 'pointer')
        .attr('title', 'Click to copy')
        .off('click')
        .on('click', function(e) {
            e.stopPropagation(); // Prevent card click

            // Copy to clipboard
            navigator.clipboard.writeText(value).then(function() {
                // Show feedback
                const originalText = $(selector).text();
                $(selector).text('✓ Copied!');

                setTimeout(function() {
                    $(selector).text(originalText);
                }, 1000);
            }).catch(function(err) {
                console.error('Failed to copy:', err);
            });
        });
}

function loadRecentActivity() {
    $.get('/api/dashboard/recent-activity?limit=10', function(data) {
        const container = $('#recent-activity');
        container.empty();

        if (data.length === 0) {
            container.html('<p class="text-muted">No recent activity</p>');
            return;
        }

        data.forEach(function(activity, index) {
            const statusClass = getStatusClass(activity.status);
            const timeAgo = formatTimeAgo(activity.timestamp);
            const animationDelay = index * 50;

            // Make activity items clickable to show details
            const item = `
                <div class="list-group-item list-group-item-action fade-in activity-item"
                     style="cursor: pointer; animation-delay: ${animationDelay}ms;"
                     data-session-id="${activity.session_id}"
                     data-status="${activity.status}">
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">${activity.description}</h6>
                        <small class="text-muted">${timeAgo}</small>
                    </div>
                    <span class="badge ${statusClass}">${activity.status}</span>
                </div>
            `;
            container.append(item);
        });

        // Add click event handler using event delegation
        container.off('click', '.activity-item').on('click', '.activity-item', function() {
            console.log('Activity item clicked!');
            const sessionId = $(this).data('session-id');
            const status = $(this).data('status');
            console.log('Session ID:', sessionId, 'Status:', status);
            if (sessionId) {
                console.log('Calling showActivityDetail...');
                showActivityDetail(sessionId, status);
            } else {
                console.log('No session ID found!');
            }
        });
    }).fail(function(xhr) {
        const errorMsg = xhr.status === 0 ? 'Network error. Check your connection.' : 'Failed to load activity';
        $('#recent-activity').html(`
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i> ${errorMsg}
                <button class="btn btn-sm btn-outline-danger ms-2" onclick="loadRecentActivity()">
                    <i class="bi bi-arrow-clockwise"></i> Retry
                </button>
            </div>
        `);
    });
}

// Show activity preview tooltip
function showActivityPreview(element, description) {
    // Create preview tooltip if it doesn't exist
    if ($('#activity-preview').length === 0) {
        $('body').append(`
            <div id="activity-preview" style="
                position: fixed;
                background: rgba(0, 0, 0, 0.8);
                color: white;
                padding: 8px 12px;
                border-radius: 4px;
                font-size: 12px;
                z-index: 10000;
                pointer-events: none;
                max-width: 300px;
                display: none;
            "></div>
        `);
    }

    const preview = $('#activity-preview');
    preview.text(description).show();

    // Position tooltip near mouse
    $(element).mousemove(function(e) {
        preview.css({
            top: e.clientY + 15 + 'px',
            left: e.clientX + 15 + 'px'
        });
    });
}

// Hide activity preview tooltip
function hideActivityPreview() {
    $('#activity-preview').hide();
}

function loadTopChannels() {
    $.get('/api/dashboard/channels-summary?limit=10', function(data) {
        const container = $('#top-channels');
        container.empty();

        if (data.length === 0) {
            container.html('<p class="text-muted">No channels yet</p>');
            return;
        }

        data.forEach(function(channel, index) {
            // Add animation delay for staggered effect
            const animationDelay = index * 50;

            const item = `
                <div class="list-group-item list-group-item-action fade-in channel-item"
                     style="cursor: pointer; animation-delay: ${animationDelay}ms;"
                     data-channel-id="${channel.channel_id}"
                     data-channel-name="${channel.channel_name}">
                    <div class="d-flex w-100 justify-content-between align-items-center">
                        <div>
                            <h6 class="mb-1">${channel.channel_name}</h6>
                            <small class="text-muted">Last crawled: ${channel.last_crawled}</small>
                        </div>
                        <span class="badge bg-primary">${channel.video_count} videos</span>
                    </div>
                </div>
            `;
            container.append(item);
        });

        // Add click event handler using event delegation
        container.off('click', '.channel-item').on('click', '.channel-item', function(e) {
            console.log('Channel item clicked!');
            // Prevent right-click from triggering
            if (e.which === 3) return;

            const channelId = $(this).data('channel-id');
            console.log('Channel ID:', channelId);
            if (channelId) {
                console.log('Calling showChannelDetail...');
                showChannelDetail(channelId);
            } else {
                console.log('No channel ID found!');
            }
        });

        // Add right-click context menu
        container.off('contextmenu', '.channel-item').on('contextmenu', '.channel-item', function(e) {
            e.preventDefault();
            const channelId = $(this).data('channel-id');
            const channelName = $(this).data('channel-name');
            showChannelContextMenu(e, channelId, channelName);
        });
    }).fail(function() {
        $('#top-channels').html('<p class="text-danger">Failed to load channels</p>');
    });
}

// Show context menu for channels
function showChannelContextMenu(event, channelId, channelName) {
    event.preventDefault();

    // Remove existing context menu
    $('.custom-context-menu').remove();

    const menu = $(`
        <div class="custom-context-menu" style="
            position: fixed;
            top: ${event.clientY}px;
            left: ${event.clientX}px;
            background: white;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            z-index: 10000;
            min-width: 200px;
        ">
            <div class="list-group list-group-flush">
                <a href="/videos?channel_id=${channelId}" class="list-group-item list-group-item-action">
                    <i class="bi bi-collection-play"></i> View Videos
                </a>
                <a href="/channels" class="list-group-item list-group-item-action">
                    <i class="bi bi-pencil"></i> Edit Channel
                </a>
                <a href="#" class="list-group-item list-group-item-action" onclick="copyChannelName('${channelName}'); return false;">
                    <i class="bi bi-clipboard"></i> Copy Name
                </a>
                <a href="#" class="list-group-item list-group-item-action" onclick="startChannelCrawl(${channelId}, '${channelName}'); return false;">
                    <i class="bi bi-play-circle"></i> Start Crawl
                </a>
            </div>
        </div>
    `);

    $('body').append(menu);

    // Close menu on click outside
    $(document).one('click', function() {
        menu.remove();
    });
}

// Copy channel name to clipboard
function copyChannelName(channelName) {
    navigator.clipboard.writeText(channelName).then(function() {
        showNotification('Channel name copied!', 'success');
    });
}

// Start crawl for specific channel
function startChannelCrawl(channelId, channelName) {
    $('#newCrawlModal').modal('show');
    // Pre-select the channel
    setTimeout(function() {
        $(`#channelSelect option[value="${channelId}"]`).prop('selected', true);
        updateSessionName();
        updateSelectedCount();
    }, 500);
}

// Show notification
function showNotification(message, type = 'info') {
    const notification = $(`
        <div class="alert alert-${type} alert-dismissible fade show"
             style="position: fixed; top: 20px; right: 20px; z-index: 10001; min-width: 250px;"
             role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `);

    $('body').append(notification);

    // Auto-dismiss after 3 seconds
    setTimeout(function() {
        notification.alert('close');
    }, 3000);
}

// Show channel detail modal
function showChannelDetail(channelId) {
    // Show modal
    $('#channelDetailModal').modal('show');

    // Reset modal content
    $('#channelDetailBody').html(`
        <div class="text-center">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-2">Loading channel details...</p>
        </div>
    `);

    // Fetch channel details
    $.get(`/api/channels/${channelId}`, function(channel) {
        const lastCrawled = channel.last_crawled_at ? new Date(channel.last_crawled_at).toLocaleString() : 'Never';
        const createdAt = new Date(channel.created_at).toLocaleString();

        const keywords = channel.keywords && channel.keywords.length > 0
            ? channel.keywords.map(k => `<span class="badge bg-secondary me-1">${k}</span>`).join('')
            : '<span class="text-muted">No keywords</span>';

        const crawlStatus = channel.crawl_enabled
            ? '<span class="badge bg-success">Enabled</span>'
            : '<span class="badge bg-secondary">Disabled</span>';

        const html = `
            <div class="row">
                <div class="col-md-12">
                    <h4>${channel.channel_name}</h4>
                    <p class="text-muted">${channel.description || 'No description available'}</p>
                </div>
            </div>

            <div class="row mt-3">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-subtitle mb-2 text-muted">Channel Information</h6>
                            <table class="table table-sm">
                                <tr>
                                    <td><strong>Platform:</strong></td>
                                    <td><span class="badge bg-info">${channel.platform || 'youtube'}</span></td>
                                </tr>
                                <tr>
                                    <td><strong>Channel URL:</strong></td>
                                    <td><a href="${channel.channel_url}" target="_blank" class="text-truncate d-inline-block" style="max-width: 200px;">${channel.channel_url}</a></td>
                                </tr>
                                <tr>
                                    <td><strong>YouTube ID:</strong></td>
                                    <td><code>${channel.youtube_channel_id || 'Not set'}</code></td>
                                </tr>
                                <tr>
                                    <td><strong>Crawl Status:</strong></td>
                                    <td>${crawlStatus}</td>
                                </tr>
                                <tr>
                                    <td><strong>Crawl Frequency:</strong></td>
                                    <td>${channel.crawl_frequency || 'daily'}</td>
                                </tr>
                            </table>
                        </div>
                    </div>
                </div>

                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-subtitle mb-2 text-muted">Statistics</h6>
                            <table class="table table-sm">
                                <tr>
                                    <td><strong>Total Videos:</strong></td>
                                    <td><span class="badge bg-primary">${channel.video_count || 0}</span></td>
                                </tr>
                                <tr>
                                    <td><strong>Last Crawled:</strong></td>
                                    <td>${lastCrawled}</td>
                                </tr>
                                <tr>
                                    <td><strong>Created:</strong></td>
                                    <td>${createdAt}</td>
                                </tr>
                                <tr>
                                    <td><strong>Keywords:</strong></td>
                                    <td>${keywords}</td>
                                </tr>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        `;

        $('#channelDetailBody').html(html);
        $('#channelDetailTitle').text(`Channel: ${channel.channel_name}`);

        // Set up view videos button
        $('#viewChannelVideosBtn').off('click').on('click', function() {
            window.location.href = `/videos?channel_id=${channelId}`;
        });
    }).fail(function(xhr) {
        $('#channelDetailBody').html(`
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i> Failed to load channel details
                <button class="btn btn-sm btn-outline-danger ms-2" onclick="showChannelDetail(${channelId})">
                    <i class="bi bi-arrow-clockwise"></i> Retry
                </button>
            </div>
        `);
    });
}

// Show activity detail modal
function showActivityDetail(sessionId, status) {
    if (!sessionId) {
        showNotification('No session information available', 'warning');
        return;
    }

    // Show modal
    $('#activityDetailModal').modal('show');

    // Reset modal content
    $('#activityDetailBody').html(`
        <div class="text-center">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-2">Loading activity details...</p>
        </div>
    `);

    // Fetch session details
    $.get(`/api/sessions/${sessionId}`, function(session) {
        const createdAt = new Date(session.created_at).toLocaleString();
        const startedAt = session.started_at ? new Date(session.started_at).toLocaleString() : 'Not started';
        const completedAt = session.completed_at ? new Date(session.completed_at).toLocaleString() : 'Not completed';

        const statusClass = getStatusClass(session.status);
        const keywords = session.filter_keywords && session.filter_keywords.length > 0
            ? session.filter_keywords.map(k => `<span class="badge bg-secondary me-1">${k}</span>`).join('')
            : '<span class="text-muted">No keywords</span>';

        // Calculate duration if completed
        let duration = 'N/A';
        if (session.started_at && session.completed_at) {
            const start = new Date(session.started_at);
            const end = new Date(session.completed_at);
            const diffMs = end - start;
            const diffMins = Math.floor(diffMs / 60000);
            const diffSecs = Math.floor((diffMs % 60000) / 1000);
            duration = `${diffMins}m ${diffSecs}s`;
        }

        const html = `
            <div class="row">
                <div class="col-md-12">
                    <h4>${session.session_name}</h4>
                    <span class="badge ${statusClass} mb-3">${session.status}</span>
                </div>
            </div>

            <div class="row">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-subtitle mb-2 text-muted">Session Information</h6>
                            <table class="table table-sm">
                                <tr>
                                    <td><strong>Session ID:</strong></td>
                                    <td><code>#${session.id}</code></td>
                                </tr>
                                <tr>
                                    <td><strong>Type:</strong></td>
                                    <td><span class="badge bg-info">${session.session_type}</span></td>
                                </tr>
                                <tr>
                                    <td><strong>Created:</strong></td>
                                    <td>${createdAt}</td>
                                </tr>
                                <tr>
                                    <td><strong>Started:</strong></td>
                                    <td>${startedAt}</td>
                                </tr>
                                <tr>
                                    <td><strong>Completed:</strong></td>
                                    <td>${completedAt}</td>
                                </tr>
                                <tr>
                                    <td><strong>Duration:</strong></td>
                                    <td>${duration}</td>
                                </tr>
                            </table>
                        </div>
                    </div>
                </div>

                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-subtitle mb-2 text-muted">Progress & Results</h6>
                            <table class="table table-sm">
                                <tr>
                                    <td><strong>Channels:</strong></td>
                                    <td><span class="badge bg-primary">${session.channel_ids ? session.channel_ids.length : 0}</span></td>
                                </tr>
                                <tr>
                                    <td><strong>Videos Processed:</strong></td>
                                    <td><span class="badge bg-success">${session.videos_processed || 0}</span></td>
                                </tr>
                                <tr>
                                    <td><strong>Videos Summarized:</strong></td>
                                    <td><span class="badge bg-info">${session.videos_summarized || 0}</span></td>
                                </tr>
                                <tr>
                                    <td><strong>Errors:</strong></td>
                                    <td><span class="badge bg-danger">${session.error_count || 0}</span></td>
                                </tr>
                                <tr>
                                    <td><strong>Max Videos/Crawl:</strong></td>
                                    <td>${session.max_videos_per_crawl || 'N/A'}</td>
                                </tr>
                                <tr>
                                    <td><strong>Filter Keywords:</strong></td>
                                    <td>${keywords}</td>
                                </tr>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

            ${session.error_message ? `
            <div class="row mt-3">
                <div class="col-md-12">
                    <div class="alert alert-danger">
                        <strong>Error Message:</strong><br>
                        ${session.error_message}
                    </div>
                </div>
            </div>
            ` : ''}
        `;

        $('#activityDetailBody').html(html);
        $('#activityDetailTitle').text(`Session: ${session.session_name}`);

        // Set up view session button
        $('#viewSessionDetailsBtn').off('click').on('click', function() {
            window.location.href = `/sessions`;
        });
    }).fail(function(xhr) {
        $('#activityDetailBody').html(`
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle"></i> Failed to load activity details
                <button class="btn btn-sm btn-outline-danger ms-2" onclick="showActivityDetail(${sessionId}, '${status}')">
                    <i class="bi bi-arrow-clockwise"></i> Retry
                </button>
            </div>
        `);
    });
}

function loadDailyChart() {
    $.get('/api/dashboard/daily-summary?days=7', function(data) {
        const ctx = document.getElementById('dailyChart').getContext('2d');

        // Reverse data to show oldest to newest
        data.reverse();

        const labels = data.map(d => d.date);
        const videosCrawled = data.map(d => d.videos_crawled);
        const videosSummarized = data.map(d => d.videos_summarized);

        if (dailyChart) {
            dailyChart.destroy();
        }

        dailyChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Videos Crawled',
                        data: videosCrawled,
                        borderColor: 'rgb(75, 192, 192)',
                        backgroundColor: 'rgba(75, 192, 192, 0.2)',
                        tension: 0.1,
                        pointRadius: 5,
                        pointHoverRadius: 8,
                        pointHitRadius: 10
                    },
                    {
                        label: 'Videos Summarized',
                        data: videosSummarized,
                        borderColor: 'rgb(255, 99, 132)',
                        backgroundColor: 'rgba(255, 99, 132, 0.2)',
                        tension: 0.1,
                        pointRadius: 5,
                        pointHoverRadius: 8,
                        pointHitRadius: 10
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'top',
                        onClick: function(e, legendItem, legend) {
                            // Navigate to videos page when clicking legend
                            window.location.href = '/videos';
                        },
                        onHover: function(e) {
                            e.native.target.style.cursor = 'pointer';
                        },
                        onLeave: function(e) {
                            e.native.target.style.cursor = 'default';
                        }
                    },
                    title: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            afterLabel: function(context) {
                                return 'Click to view videos';
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                },
                onClick: function(evt, activeElements) {
                    if (activeElements.length > 0) {
                        // Navigate to videos page when clicking on data points
                        window.location.href = '/videos';
                    }
                },
                onHover: function(evt, activeElements) {
                    evt.native.target.style.cursor = activeElements.length > 0 ? 'pointer' : 'default';
                }
            }
        });
    }).fail(function() {
        console.error('Failed to load daily chart data');
    });
}

function loadChannelsForCrawl() {
    $.get('/api/channels?limit=100', function(data) {
        // Store all channels globally for filtering/sorting
        window.allChannels = data;

        // Initial render
        renderChannelList();

        // Update session name when channels or keywords change
        $('#channelSelect').change(function() {
            updateSessionName();
            updateSelectedCount();
        });
        $('#filterKeywords').on('input', updateSessionName);
        $('#maxVideos').on('input', updateSessionName);

        // Search functionality
        $('#channelSearch').on('input', function() {
            renderChannelList();
        });

        // Sort functionality
        $('#channelSort').change(function() {
            renderChannelList();
        });
    }).fail(function() {
        console.error('Failed to load channels');
    });
}

function renderChannelList() {
    const searchTerm = $('#channelSearch').val().toLowerCase();
    const sortBy = $('#channelSort').val();
    const select = $('#channelSelect');

    // Get currently selected values to preserve selection
    const selectedValues = select.val() || [];

    // Filter channels by search term
    let filteredChannels = window.allChannels.filter(function(channel) {
        return channel.channel_name.toLowerCase().includes(searchTerm);
    });

    // Sort channels
    filteredChannels.sort(function(a, b) {
        switch(sortBy) {
            case 'name-asc':
                return a.channel_name.localeCompare(b.channel_name);
            case 'name-desc':
                return b.channel_name.localeCompare(a.channel_name);
            case 'videos-desc':
                return (b.video_count || 0) - (a.video_count || 0);
            case 'videos-asc':
                return (a.video_count || 0) - (b.video_count || 0);
            case 'recent':
                const dateA = a.last_crawled_at ? new Date(a.last_crawled_at) : new Date(0);
                const dateB = b.last_crawled_at ? new Date(b.last_crawled_at) : new Date(0);
                return dateB - dateA;
            default:
                return 0;
        }
    });

    // Clear and repopulate select
    select.empty();

    if (filteredChannels.length === 0) {
        select.append('<option disabled>No channels found</option>');
    } else {
        filteredChannels.forEach(function(channel) {
            const videoInfo = channel.video_count ? ` (${channel.video_count} videos)` : ' (0 videos)';
            const option = $('<option></option>')
                .val(channel.id)
                .attr('data-name', channel.channel_name)
                .attr('data-videos', channel.video_count || 0)
                .text(channel.channel_name + videoInfo);

            // Restore selection if it was previously selected
            if (selectedValues.includes(channel.id.toString())) {
                option.prop('selected', true);
            }

            select.append(option);
        });
    }

    updateSelectedCount();
}

function selectAllChannels() {
    $('#channelSelect option').prop('selected', true);
    updateSessionName();
    updateSelectedCount();
}

function deselectAllChannels() {
    $('#channelSelect option').prop('selected', false);
    updateSessionName();
    updateSelectedCount();
}

function updateSelectedCount() {
    const count = $('#channelSelect option:selected').length;
    $('#selectedCount').text(count);
}

function updateSessionName() {
    const selectedOptions = $('#channelSelect option:selected');
    const keywords = $('#filterKeywords').val().trim();
    const maxVideos = $('#maxVideos').val();

    if (selectedOptions.length === 0) {
        $('#sessionName').val('');
        return;
    }

    // Get channel names
    const channelNames = [];
    selectedOptions.each(function() {
        channelNames.push($(this).data('name'));
    });

    // Format: "ChannelName1, ChannelName2 - 2026-02-07 23:45 - keyword1, keyword2 - Max5"
    const now = new Date();
    const dateStr = now.toISOString().slice(0, 10); // YYYY-MM-DD
    const timeStr = now.toTimeString().slice(0, 5); // HH:MM

    let sessionName = channelNames.join(', ') + ' - ' + dateStr + ' ' + timeStr;

    if (keywords) {
        sessionName += ' - ' + keywords;
    }

    sessionName += ' - Max' + maxVideos;

    $('#sessionName').val(sessionName);
}

function startCrawl() {
    const sessionName = $('#sessionName').val();
    const selectedChannels = $('#channelSelect').val();
    const keywords = $('#filterKeywords').val();
    const maxVideos = parseInt($('#maxVideos').val()) || 5;

    if (!sessionName || !selectedChannels || selectedChannels.length === 0) {
        alert('Please fill in all required fields');
        return;
    }

    const keywordsList = keywords ? keywords.split(',').map(k => k.trim()).filter(k => k) : [];

    const payload = {
        session_name: sessionName,
        session_type: 'manual',
        channel_ids: selectedChannels.map(id => parseInt(id)),
        filter_keywords: keywordsList,
        max_videos_per_crawl: maxVideos
    };

    $.ajax({
        url: '/api/sessions',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(payload),
        success: function(response) {
            alert('Crawl session started successfully!');
            $('#newCrawlModal').modal('hide');
            $('#newCrawlForm')[0].reset();

            // Redirect to sessions page
            window.location.href = '/sessions';
        },
        error: function(xhr) {
            alert('Failed to start crawl session: ' + (xhr.responseJSON?.detail || 'Unknown error'));
        }
    });
}

function refreshDashboard() {
    // Show loading indicator
    showLoadingIndicator();

    // Add visual feedback
    $('body').css('opacity', '0.7');

    Promise.all([
        $.get('/api/dashboard/stats'),
        $.get('/api/dashboard/recent-activity?limit=10'),
        $.get('/api/dashboard/channels-summary?limit=10'),
        $.get('/api/dashboard/daily-summary?days=7')
    ]).then(function() {
        loadDashboardStats();
        loadRecentActivity();
        loadTopChannels();
        loadDailyChart();

        // Hide loading and restore opacity
        hideLoadingIndicator();
        $('body').css('opacity', '1');

        // Show success notification
        showNotification('Dashboard refreshed successfully!', 'success');
    }).catch(function() {
        hideLoadingIndicator();
        $('body').css('opacity', '1');
        showNotification('Failed to refresh dashboard', 'danger');
    });
}

// Show loading indicator
function showLoadingIndicator() {
    if ($('#loading-indicator').length === 0) {
        $('body').append(`
            <div id="loading-indicator" style="
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: rgba(255, 255, 255, 0.95);
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
                z-index: 10002;
                text-align: center;
            ">
                <div class="spinner-border text-primary mb-3" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <div><strong>Refreshing Dashboard...</strong></div>
            </div>
        `);
    } else {
        $('#loading-indicator').show();
    }
}

// Hide loading indicator
function hideLoadingIndicator() {
    $('#loading-indicator').fadeOut(300);
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

function formatTimeAgo(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return Math.floor(seconds / 60) + ' minutes ago';
    if (seconds < 86400) return Math.floor(seconds / 3600) + ' hours ago';
    return Math.floor(seconds / 86400) + ' days ago';
}

// Make functions globally accessible for onclick handlers
window.showChannelDetail = showChannelDetail;
window.showActivityDetail = showActivityDetail;
window.showChannelContextMenu = showChannelContextMenu;
window.copyChannelName = copyChannelName;
window.startChannelCrawl = startChannelCrawl;

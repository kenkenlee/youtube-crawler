// Dashboard JavaScript

let dailyChart = null;

// Load dashboard on page load
$(document).ready(function() {
    loadDashboardStats();
    loadRecentActivity();
    loadTopChannels();
    loadDailyChart();
    loadChannelsForCrawl();

    // Auto-refresh every 30 seconds
    setInterval(refreshDashboard, 30000);
});

function loadDashboardStats() {
    $.get('/api/dashboard/stats', function(data) {
        $('#total-channels').text(data.total_channels);
        $('#active-channels').text(data.active_channels + ' active');
        $('#total-videos').text(data.total_videos);
        $('#summarized-videos').text(data.summarized_videos + ' summarized');
        $('#active-sessions').text(data.active_sessions);
        $('#completed-sessions').text(data.completed_sessions);
        $('#failed-sessions').text(data.failed_sessions + ' failed');
    }).fail(function() {
        console.error('Failed to load dashboard stats');
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

        data.forEach(function(activity) {
            const statusClass = getStatusClass(activity.status);
            const timeAgo = formatTimeAgo(activity.timestamp);

            const item = `
                <div class="list-group-item">
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">${activity.description}</h6>
                        <small class="text-muted">${timeAgo}</small>
                    </div>
                    <span class="badge ${statusClass}">${activity.status}</span>
                </div>
            `;
            container.append(item);
        });
    }).fail(function() {
        $('#recent-activity').html('<p class="text-danger">Failed to load activity</p>');
    });
}

function loadTopChannels() {
    $.get('/api/dashboard/channels-summary?limit=10', function(data) {
        const container = $('#top-channels');
        container.empty();

        if (data.length === 0) {
            container.html('<p class="text-muted">No channels yet</p>');
            return;
        }

        data.forEach(function(channel) {
            const item = `
                <div class="list-group-item">
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">${channel.channel_name}</h6>
                        <span class="badge bg-primary">${channel.video_count} videos</span>
                    </div>
                    <small class="text-muted">Last crawled: ${channel.last_crawled}</small>
                </div>
            `;
            container.append(item);
        });
    }).fail(function() {
        $('#top-channels').html('<p class="text-danger">Failed to load channels</p>');
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
                        tension: 0.1
                    },
                    {
                        label: 'Videos Summarized',
                        data: videosSummarized,
                        borderColor: 'rgb(255, 99, 132)',
                        backgroundColor: 'rgba(255, 99, 132, 0.2)',
                        tension: 0.1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    title: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }).fail(function() {
        console.error('Failed to load daily chart data');
    });
}

function loadChannelsForCrawl() {
    $.get('/api/channels?limit=100', function(data) {
        const select = $('#channelSelect');
        select.empty();

        data.forEach(function(channel) {
            select.append(`<option value="${channel.id}" data-name="${channel.channel_name}">${channel.channel_name}</option>`);
        });

        // Update session name when channels or keywords change
        select.change(updateSessionName);
        $('#filterKeywords').on('input', updateSessionName);
        $('#maxVideos').on('input', updateSessionName);
    }).fail(function() {
        console.error('Failed to load channels');
    });
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
        max_videos_per_channel: maxVideos
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
    loadDashboardStats();
    loadRecentActivity();
    loadTopChannels();
    loadDailyChart();
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

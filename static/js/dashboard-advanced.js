// ============================================
// ADVANCED DASHBOARD FEATURES
// ============================================

// Dark Mode
function initializeDarkMode() {
    const darkMode = localStorage.getItem('darkMode') === 'true';
    if (darkMode) {
        $('body').addClass('dark-mode');
        $('#darkModeToggle').prop('checked', true);
    }

    $('#darkModeToggle').change(function() {
        const isChecked = $(this).is(':checked');
        if (isChecked) {
            $('body').addClass('dark-mode');
            localStorage.setItem('darkMode', 'true');
            showNotification('Dark mode enabled', 'info');
        } else {
            $('body').removeClass('dark-mode');
            localStorage.setItem('darkMode', 'false');
            showNotification('Light mode enabled', 'info');
        }
    });
}

// Auto-refresh
function initializeAutoRefresh() {
    const autoRefresh = localStorage.getItem('autoRefresh') !== 'false';
    $('#autoRefreshToggle').prop('checked', autoRefresh);

    $('#autoRefreshToggle').change(function() {
        const isChecked = $(this).is(':checked');
        localStorage.setItem('autoRefresh', isChecked);

        if (isChecked) {
            startAutoRefresh();
            showNotification('Auto-refresh enabled', 'success');
        } else {
            stopAutoRefresh();
            showNotification('Auto-refresh disabled', 'info');
        }
    });
}

function startAutoRefresh() {
    stopAutoRefresh();

    if ($('#autoRefreshToggle').is(':checked')) {
        window.autoRefreshInterval = setInterval(function() {
            refreshDashboard();
        }, 30000);
    }
}

function stopAutoRefresh() {
    if (window.autoRefreshInterval) {
        clearInterval(window.autoRefreshInterval);
        window.autoRefreshInterval = null;
    }
}

// Update last updated time
function updateLastUpdatedTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString();
    $('#lastUpdated').text(timeString);
}

// Filters
function initializeFilters() {
    $('#dateRangeFilter').change(function() {
        const value = $(this).val();
        if (value === 'custom') {
            $('#customDateRange').show();
        } else {
            $('#customDateRange').hide();
        }
    });
}

function applyFilters() {
    window.dashboardFilters = {
        dateRange: $('#dateRangeFilter').val(),
        status: $('#statusFilter').val(),
        keywords: $('#searchKeywords').val()
    };

    $('#filterModal').modal('hide');
    loadRecentActivity();

    if (window.dashboardFilters.status !== 'all' || window.dashboardFilters.keywords) {
        $('[data-bs-target="#filterModal"]').addClass('filter-active');
    }

    showNotification('Filters applied', 'success');
}

function clearFilters() {
    window.dashboardFilters = {
        dateRange: 'week',
        status: 'all',
        keywords: ''
    };

    $('#dateRangeFilter').val('week');
    $('#statusFilter').val('all');
    $('#searchKeywords').val('');
    $('#customDateRange').hide();

    $('[data-bs-target="#filterModal"]').removeClass('filter-active');
    $('#filterModal').modal('hide');
    loadRecentActivity();

    showNotification('Filters cleared', 'info');
}

// Export functionality
function exportDashboardData() {
    $('#exportModal').modal('show');
}

function exportData(format) {
    const button = event.target.closest('button');
    $(button).addClass('btn-export-loading').prop('disabled', true);

    Promise.all([
        $.get('/api/dashboard/stats'),
        $.get('/api/dashboard/recent-activity?limit=100'),
        $.get('/api/dashboard/channels-summary?limit=100'),
        $.get('/api/dashboard/daily-summary?days=30')
    ]).then(function(results) {
        const [stats, activities, channels, dailySummary] = results;

        const dashboardData = {
            exportDate: new Date().toISOString(),
            statistics: stats,
            recentActivities: activities,
            topChannels: channels,
            dailySummary: dailySummary
        };

        if (format === 'json') {
            downloadJSON(dashboardData);
        } else if (format === 'csv') {
            downloadCSV(dashboardData);
        } else if (format === 'summary') {
            downloadSummaryReport(dashboardData);
        }

        $(button).removeClass('btn-export-loading').prop('disabled', false);
        $('#exportModal').modal('hide');
        showNotification('Data exported successfully', 'success');
    }).catch(function() {
        $(button).removeClass('btn-export-loading').prop('disabled', false);
        showNotification('Export failed', 'danger');
    });
}

function downloadJSON(data) {
    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'dashboard-export-' + new Date().toISOString().split('T')[0] + '.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function downloadCSV(data) {
    let csv = 'Dashboard Export\n\n';

    csv += 'Statistics\n';
    csv += 'Metric,Value\n';
    csv += 'Total Channels,' + data.statistics.total_channels + '\n';
    csv += 'Active Channels,' + data.statistics.active_channels + '\n';
    csv += 'Total Videos,' + data.statistics.total_videos + '\n';
    csv += 'Summarized Videos,' + data.statistics.summarized_videos + '\n';
    csv += 'Active Sessions,' + data.statistics.active_sessions + '\n';
    csv += 'Completed Sessions,' + data.statistics.completed_sessions + '\n';
    csv += 'Failed Sessions,' + data.statistics.failed_sessions + '\n\n';

    csv += 'Recent Activities\n';
    csv += 'Timestamp,Type,Description,Status\n';
    data.recentActivities.forEach(function(activity) {
        csv += '"' + activity.timestamp + '","' + activity.activity_type + '","' + activity.description + '","' + activity.status + '"\n';
    });
    csv += '\n';

    csv += 'Top Channels\n';
    csv += 'Channel Name,Video Count,Last Crawled\n';
    data.topChannels.forEach(function(channel) {
        csv += '"' + channel.channel_name + '",' + channel.video_count + ',"' + channel.last_crawled + '"\n';
    });

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'dashboard-export-' + new Date().toISOString().split('T')[0] + '.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function downloadSummaryReport(data) {
    let report = '============================================================\n';
    report += 'YOUTUBE CRAWLER - DASHBOARD SUMMARY REPORT\n';
    report += '============================================================\n\n';
    report += 'Generated: ' + new Date().toLocaleString() + '\n\n';

    report += 'OVERVIEW STATISTICS\n';
    report += '------------------------------------------------------------\n';
    report += 'Total Channels: ' + data.statistics.total_channels + ' (' + data.statistics.active_channels + ' active)\n';
    report += 'Total Videos: ' + data.statistics.total_videos + ' (' + data.statistics.summarized_videos + ' summarized)\n';
    report += 'Sessions: ' + data.statistics.completed_sessions + ' completed, ' + data.statistics.active_sessions + ' active, ' + data.statistics.failed_sessions + ' failed\n\n';

    report += 'TOP CHANNELS\n';
    report += '------------------------------------------------------------\n';
    data.topChannels.slice(0, 10).forEach(function(channel, index) {
        report += (index + 1) + '. ' + channel.channel_name + ' - ' + channel.video_count + ' videos\n';
        report += '   Last crawled: ' + channel.last_crawled + '\n';
    });
    report += '\n';

    report += 'RECENT ACTIVITY (Last 10)\n';
    report += '------------------------------------------------------------\n';
    data.recentActivities.slice(0, 10).forEach(function(activity, index) {
        report += (index + 1) + '. [' + activity.status.toUpperCase() + '] ' + activity.description + '\n';
        report += '   ' + new Date(activity.timestamp).toLocaleString() + '\n';
    });
    report += '\n';

    report += 'DAILY SUMMARY (Last 7 Days)\n';
    report += '------------------------------------------------------------\n';
    data.dailySummary.slice(0, 7).reverse().forEach(function(day) {
        report += day.date + ': ' + day.videos_crawled + ' videos crawled, ' + day.videos_summarized + ' summarized\n';
    });
    report += '\n';

    report += '============================================================\n';
    report += 'End of Report\n';
    report += '============================================================\n';

    const blob = new Blob([report], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'dashboard-summary-' + new Date().toISOString().split('T')[0] + '.txt';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// Floating Action Button
function toggleFabMenu() {
    const menu = $('#fabMenu');
    const button = $('#fabButton');

    if (menu.is(':visible')) {
        menu.fadeOut(200);
        button.removeClass('active');
    } else {
        menu.fadeIn(200);
        button.addClass('active');
    }
}

// Close FAB menu when clicking outside
$(document).click(function(event) {
    if (!$(event.target).closest('.fab-container').length) {
        $('#fabMenu').fadeOut(200);
        $('#fabButton').removeClass('active');
    }
});

// Make functions globally accessible
window.initializeDarkMode = initializeDarkMode;
window.initializeAutoRefresh = initializeAutoRefresh;
window.initializeFilters = initializeFilters;
window.startAutoRefresh = startAutoRefresh;
window.stopAutoRefresh = stopAutoRefresh;
window.updateLastUpdatedTime = updateLastUpdatedTime;
window.exportDashboardData = exportDashboardData;
window.exportData = exportData;
window.applyFilters = applyFilters;
window.clearFilters = clearFilters;
window.toggleFabMenu = toggleFabMenu;
window.downloadJSON = downloadJSON;
window.downloadCSV = downloadCSV;
window.downloadSummaryReport = downloadSummaryReport;

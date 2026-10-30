// Categories / Channel management (stats + per-category add/remove + bulk assign)

let statsCache = null;
let allChannels = [];
let selectedIds = new Set();
let manageCatId = null;
let categoryMembers = [];

$(document).ready(function() {
    refreshAll();
    $('#channelFilter').on('input', renderAssignList);
    $('#channelCatFilter').on('change', renderAssignList);
    $('#memberFilter').on('input', renderMemberList);
    $('#existingSearch').on('input', renderExistingPickList);
    $('#selectAllVisible').on('change', function() {
        const on = $(this).is(':checked');
        $('#assignChannelList .ch-check:visible').each(function() {
            const id = Number($(this).val());
            $(this).prop('checked', on);
            if (on) selectedIds.add(id); else selectedIds.delete(id);
        });
        updateSelCount();
    });
});

function redirectToLogin() { window.location.href = '/settings/login'; }

function esc(s) {
    return String(s == null ? '' : s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function refreshAll() {
    loadStats();
    loadChannelsForAssign();
    if (manageCatId) loadCategoryMembers(manageCatId);
}

function loadStats() {
    $.get('/api/settings/catalog-stats', function(s) {
        statsCache = s;
        const t = s.totals || {};
        $('#statCategories').text((t.categories ?? 0).toLocaleString());
        $('#statChannels').text((t.channels ?? 0).toLocaleString());
        $('#statChannelsDetail').text(
            (t.channels_crawl_enabled ?? 0).toLocaleString() + ' enabled · ' +
            (t.channels_crawl_disabled ?? 0).toLocaleString() + ' disabled'
        );
        $('#statVideos').text((t.videos ?? 0).toLocaleString());
        $('#statVideosDetail').text(
            (t.videos_with_transcript ?? 0).toLocaleString() + ' transcript · ' +
            (t.videos_with_summary ?? 0).toLocaleString() + ' summary'
        );
        $('#statUncategorized').text((t.channels_uncategorized ?? 0).toLocaleString());
        $('#statEnabled').text((t.channels_crawl_enabled ?? 0).toLocaleString());
        $('#statDisabled').text((t.channels_crawl_disabled ?? 0).toLocaleString());
        $('#statCrawled7d').text((t.channels_crawled_last_7d ?? 0).toLocaleString());
        $('#statNeverCrawled').text((t.channels_never_crawled ?? 0).toLocaleString());
        $('#statRecent').text(
            (t.videos_created_last_7d ?? 0).toLocaleString() + ' / ' +
            (t.videos_created_last_30d ?? 0).toLocaleString()
        );
        $('#statsMeta').text('Generated ' + (s.generated_at || '—') + ' (' + (s.timezone || 'Asia/Shanghai') + ')');

        const cats = s.by_category || [];
        $('#catCountLabel').text(cats.length + ' categories');
        renderCategoryTable(cats);
        fillCategorySelects(cats);
    }).fail(function(xhr) {
        if (xhr.status === 401) { redirectToLogin(); return; }
        $('#categoryBody').html('<tr><td colspan="6" class="text-danger px-3">Failed to load stats</td></tr>');
    });
}

function renderCategoryTable(cats) {
    if (!cats.length) {
        $('#categoryBody').html('<tr><td colspan="6" class="text-muted px-3">No categories</td></tr>');
        return;
    }
    $('#categoryBody').html(cats.map(function(c) {
        const active = manageCatId === c.id ? ' table-active' : '';
        return '<tr class="' + active + '" data-cat-id="' + c.id + '">' +
            '<td class="ps-3"><strong>' + esc(c.name_zh || c.slug) + '</strong>' +
            '<div class="small text-muted">' + esc(c.name_en || '') + '</div></td>' +
            '<td class="d-none d-md-table-cell"><code>' + esc(c.slug) + '</code></td>' +
            '<td class="text-end">' + Number(c.channel_count || 0).toLocaleString() + '</td>' +
            '<td class="text-end">' + Number(c.channels_enabled || 0).toLocaleString() + '</td>' +
            '<td class="text-end">' + Number(c.video_count || 0).toLocaleString() + '</td>' +
            '<td class="text-end pe-3 text-nowrap">' +
            '<button class="btn btn-sm btn-outline-primary me-1" title="Manage channels" onclick="selectManageCategory(' + c.id + ')"><i class="bi bi-people"></i></button>' +
            '<button class="btn btn-sm btn-outline-secondary me-1" title="Edit" onclick="openEditCategory(' + c.id + ')"><i class="bi bi-pencil"></i></button>' +
            '<button class="btn btn-sm btn-outline-danger" title="Delete category" onclick="deleteCategory(' + c.id + ', \'' + esc(c.slug) + '\')"><i class="bi bi-trash"></i></button>' +
            '</td></tr>';
    }).join(''));
}

function fillCategorySelects(cats) {
    const opts = cats.map(function(c) {
        return '<option value="' + c.id + '">' + esc(c.name_zh || c.slug) + ' (' + (c.channel_count || 0) + ')</option>';
    }).join('');
    const prevAssign = $('#assignCategorySelect').val();
    $('#assignCategorySelect').html(opts);
    if (prevAssign) $('#assignCategorySelect').val(prevAssign);

    const manageOpts = '<option value="">— Select category —</option>' + opts;
    const prevManage = manageCatId ? String(manageCatId) : '';
    $('#manageCategorySelect').html(manageOpts);
    if (prevManage) $('#manageCategorySelect').val(prevManage);

    const filter = '<option value="">All channels</option><option value="__none__">Uncategorized only</option>' +
        cats.map(function(c) {
            return '<option value="' + c.id + '">' + esc(c.name_zh || c.slug) + '</option>';
        }).join('');
    const prev = $('#channelCatFilter').val();
    $('#channelCatFilter').html(filter);
    if (prev) $('#channelCatFilter').val(prev);
}

function catMeta(id) {
    const cats = (statsCache && statsCache.by_category) || [];
    return cats.find(function(c) { return c.id === Number(id); }) || null;
}

function selectManageCategory(id) {
    manageCatId = Number(id);
    $('#manageCategorySelect').val(String(manageCatId));
    $('#btnAddExisting, #btnAddNew').prop('disabled', false);
    const c = catMeta(manageCatId);
    $('#manageCatHint').html(
        'Managing <strong>' + esc(c ? (c.name_zh || c.slug) : ('#' + manageCatId)) + '</strong>' +
        (c ? ' <code class="ms-1">' + esc(c.slug) + '</code>' : '') +
        '. Add existing crawler channels, or create from YouTube URL/search.'
    );
    if (statsCache && statsCache.by_category) renderCategoryTable(statsCache.by_category);
    loadCategoryMembers(manageCatId);
    document.getElementById('categoryMemberList').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function onManageCategoryChange() {
    const v = $('#manageCategorySelect').val();
    if (!v) {
        manageCatId = null;
        categoryMembers = [];
        $('#btnAddExisting, #btnAddNew').prop('disabled', true);
        $('#manageCatHint').text('Select a category above (or click Channels on a row) to add or remove channels for that category.');
        $('#categoryMemberList').html('<p class="text-muted p-3 mb-0">No category selected.</p>');
        $('#memberCountLabel').text('');
        if (statsCache && statsCache.by_category) renderCategoryTable(statsCache.by_category);
        return;
    }
    selectManageCategory(Number(v));
}

function loadCategoryMembers(catId) {
    $('#categoryMemberList').html('<p class="text-muted p-3 mb-0"><span class="spinner-border spinner-border-sm me-1"></span>Loading…</p>');
    $.get('/api/categories/' + catId + '/channels?limit=500', function(rows) {
        categoryMembers = rows || [];
        renderMemberList();
    }).fail(function(xhr) {
        if (xhr.status === 401) { redirectToLogin(); return; }
        $('#categoryMemberList').html('<p class="text-danger p-3 mb-0">Failed to load channels</p>');
    });
}

function renderMemberList() {
    const q = ($('#memberFilter').val() || '').toLowerCase().trim();
    let rows = categoryMembers.slice();
    if (q) {
        rows = rows.filter(function(ch) {
            return (ch.channel_name || '').toLowerCase().indexOf(q) >= 0 ||
                (ch.channel_id || '').toLowerCase().indexOf(q) >= 0;
        });
    }
    $('#memberCountLabel').text(rows.length + ' shown · ' + categoryMembers.length + ' in category');
    if (!manageCatId) {
        $('#categoryMemberList').html('<p class="text-muted p-3 mb-0">No category selected.</p>');
        return;
    }
    if (!rows.length) {
        $('#categoryMemberList').html('<p class="text-muted p-3 mb-0">No channels in this category yet. Use Add existing or Add new from YouTube.</p>');
        return;
    }
    const html = rows.map(function(ch) {
        const other = (ch.categories || []).filter(function(c) { return c.id !== manageCatId; })
            .map(function(c) { return '<span class="badge bg-light text-dark border me-1">' + esc(c.name_zh || c.slug) + '</span>'; })
            .join('');
        const thumb = ch.thumbnail_url || 'https://www.gstatic.com/youtube/img/branding/youtubelogo/svg/youtubelogo.svg';
        return '<div class="d-flex align-items-center gap-2 px-3 py-2 border-bottom">' +
            '<img src="' + esc(thumb) + '" alt="" width="36" height="36" class="rounded-circle" style="object-fit:cover" onerror="this.style.display=\'none\'">' +
            '<div class="flex-grow-1 min-w-0">' +
            '<div class="fw-semibold text-truncate">' + esc(ch.channel_name) + '</div>' +
            '<div class="small text-muted"><code>' + esc(ch.channel_id) + '</code>' +
            (other ? ' · also in ' + other : '') + '</div></div>' +
            '<span class="badge ' + (ch.crawl_enabled ? 'bg-success' : 'bg-secondary') + '">' +
            (ch.crawl_enabled ? 'On' : 'Off') + '</span>' +
            '<button class="btn btn-sm btn-outline-warning" title="Remove from this category" ' +
            'onclick="removeFromCategory(' + ch.id + ', false)">Remove</button>' +
            '<button class="btn btn-sm btn-outline-danger" title="Delete channel entirely" ' +
            'onclick="removeFromCategory(' + ch.id + ', true)"><i class="bi bi-trash"></i></button>' +
            '</div>';
    }).join('');
    $('#categoryMemberList').html(html);
}

function removeFromCategory(channelId, hardDelete) {
    if (!manageCatId) return;
    const ch = categoryMembers.find(function(x) { return x.id === channelId; });
    const name = ch ? ch.channel_name : ('#' + channelId);
    if (hardDelete) {
        if (!confirm('Permanently DELETE channel "' + name + '" and all its videos from the crawler? This cannot be undone.')) return;
    } else {
        if (!confirm('Remove "' + name + '" from this category only? (Channel stays in the crawler / other categories.)')) return;
    }
    const url = '/api/categories/' + manageCatId + '/channels/' + channelId + (hardDelete ? '?hard_delete=true' : '');
    $.ajax({ url: url, method: 'DELETE' })
        .done(function() { refreshAll(); })
        .fail(function(xhr) {
            if (xhr.status === 401) { redirectToLogin(); return; }
            alert('Remove failed: ' + (xhr.responseJSON && xhr.responseJSON.detail || xhr.statusText));
        });
}

function openAddExistingModal() {
    if (!manageCatId) { alert('Select a category first'); return; }
    const c = catMeta(manageCatId);
    $('#addExistingCatLabel').text(c ? (c.name_zh || c.slug) : ('#' + manageCatId));
    $('#existingSearch').val('');
    renderExistingPickList();
    new bootstrap.Modal(document.getElementById('addExistingModal')).show();
}

function renderExistingPickList() {
    const memberSet = new Set(categoryMembers.map(function(c) { return c.id; }));
    const q = ($('#existingSearch').val() || '').toLowerCase().trim();
    let rows = allChannels.filter(function(ch) { return !memberSet.has(ch.id); });
    if (q) {
        rows = rows.filter(function(ch) {
            return (ch.channel_name || '').toLowerCase().indexOf(q) >= 0 ||
                (ch.channel_id || '').toLowerCase().indexOf(q) >= 0;
        });
    }
    rows = rows.slice(0, 80);
    if (!rows.length) {
        $('#existingPickList').html('<p class="text-muted p-3 mb-0">No matching channels outside this category.</p>');
        return;
    }
    $('#existingPickList').html(rows.map(function(ch) {
        const cats = (ch.categories || []).map(function(c) {
            return '<span class="badge bg-light text-dark border me-1">' + esc(c.name_zh || c.slug) + '</span>';
        }).join('') || '<span class="text-muted small">Uncategorized</span>';
        const thumb = ch.thumbnail_url || '';
        return '<div class="d-flex align-items-center gap-2 px-3 py-2 border-bottom">' +
            (thumb ? '<img src="' + esc(thumb) + '" width="32" height="32" class="rounded-circle" style="object-fit:cover" onerror="this.style.display=\'none\'">' : '') +
            '<div class="flex-grow-1"><div class="fw-semibold">' + esc(ch.channel_name) + '</div>' +
            '<div class="small">' + cats + '</div></div>' +
            '<button class="btn btn-sm btn-success" onclick="addExistingToCategory(' + ch.id + ')">Add</button></div>';
    }).join(''));
}

function addExistingToCategory(channelId) {
    if (!manageCatId) return;
    $.ajax({
        url: '/api/categories/' + manageCatId + '/channels',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ channel_id: channelId })
    }).done(function() {
        loadCategoryMembers(manageCatId);
        loadStats();
        loadChannelsForAssign();
        renderExistingPickList();
    }).fail(function(xhr) {
        if (xhr.status === 401) { redirectToLogin(); return; }
        alert('Add failed: ' + (xhr.responseJSON && xhr.responseJSON.detail || xhr.statusText));
    });
}

function openAddNewModal() {
    if (!manageCatId) { alert('Select a category first'); return; }
    const c = catMeta(manageCatId);
    $('#addNewCatLabel').text(c ? (c.name_zh || c.slug) : ('#' + manageCatId));
    $('#ytSearchQuery').val('');
    $('#ytSearchResults').empty();
    $('#newChannelUrl').val('');
    $('#newCrawlFrequency').val('manual');
    $('#newCrawlEnabled').prop('checked', true);
    new bootstrap.Modal(document.getElementById('addNewModal')).show();
}

function searchYtForCategory() {
    const query = ($('#ytSearchQuery').val() || '').trim();
    if (query.length < 2) { alert('Enter at least 2 characters'); return; }
    const $r = $('#ytSearchResults');
    $r.html('<p class="text-muted mb-0"><span class="spinner-border spinner-border-sm me-1"></span>Searching…</p>');
    $.ajax({
        url: '/api/channels/search/youtube?q=' + encodeURIComponent(query) + '&limit=10',
        method: 'GET',
        timeout: 30000
    }).done(function(results) {
        if (!results || !results.length) {
            $r.html('<div class="alert alert-warning mb-0">No channels found.</div>');
            return;
        }
        const $list = $('<div class="list-group"></div>');
        results.forEach(function(ch) {
            const badge = ch.already_added
                ? '<span class="badge bg-secondary">Already in crawler</span>'
                : '<span class="badge bg-success">New</span>';
            const thumb = ch.thumbnail || ch.thumbnail_url || '';
            const url = ch.channel_url || ('https://www.youtube.com/channel/' + (ch.youtube_channel_id || ''));
            const $btn = $('<button type="button" class="list-group-item list-group-item-action d-flex align-items-center gap-2"></button>');
            $btn.data('url', url).data('yt-id', ch.youtube_channel_id || '');
            $btn.on('click', function() {
                pickYtResult($(this).data('url'), $(this).data('yt-id'));
            });
            let inner = '';
            if (thumb) inner += '<img src="' + esc(thumb) + '" width="40" height="40" class="rounded-circle">';
            inner += '<div class="flex-grow-1 text-start"><div class="fw-semibold">' + esc(ch.channel_name || ch.title || '') + '</div>' +
                '<div class="small text-muted">' + esc(ch.youtube_channel_id || '') + '</div></div>' + badge;
            $btn.html(inner);
            $list.append($btn);
        });
        $r.empty().append($list);
    }).fail(function(xhr) {
        $r.html('<div class="alert alert-danger mb-0">Search failed: ' +
            esc((xhr.responseJSON && xhr.responseJSON.detail) || xhr.statusText) + '</div>');
    });
}

function pickYtResult(url, ytId) {
    $('#newChannelUrl').val(url);
    if (ytId) $('#newChannelUrl').data('yt-id', ytId);
    else $('#newChannelUrl').removeData('yt-id');
}

function submitNewChannelToCategory() {
    if (!manageCatId) return;
    const url = ($('#newChannelUrl').val() || '').trim();
    const ytId = $('#newChannelUrl').data('yt-id');
    if (!url && !ytId) { alert('Paste a YouTube channel URL or pick a search result'); return; }

    const payload = {
        crawl_enabled: $('#newCrawlEnabled').is(':checked'),
        crawl_frequency: $('#newCrawlFrequency').val() || 'manual'
    };
    if (ytId) payload.youtube_channel_id = ytId;
    else payload.url = url;

    const $btn = $('#btnSubmitNewChannel');
    const original = $btn.text();
    $btn.text('Adding…').prop('disabled', true);

    $.ajax({
        url: '/api/categories/' + manageCatId + '/channels',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(payload),
        timeout: 60000
    }).done(function(ch) {
        $btn.text(original).prop('disabled', false);
        bootstrap.Modal.getInstance(document.getElementById('addNewModal')).hide();
        alert('Added: ' + (ch.channel_name || ch.channel_id));
        refreshAll();
    }).fail(function(xhr) {
        $btn.text(original).prop('disabled', false);
        if (xhr.status === 401) { redirectToLogin(); return; }
        alert('Add failed: ' + (xhr.responseJSON && xhr.responseJSON.detail || xhr.statusText));
    });
}

function loadChannelsForAssign() {
    allChannels = [];
    function page(skip) {
        $.get('/api/channels/?skip=' + skip + '&limit=200', function(rows) {
            allChannels = allChannels.concat(rows || []);
            if ((rows || []).length === 200) {
                page(skip + 200);
            } else {
                renderAssignList();
                if ($('#addExistingModal').hasClass('show')) renderExistingPickList();
            }
        }).fail(function(xhr) {
            if (xhr.status === 401) { redirectToLogin(); return; }
            $('#assignChannelList').html('<p class="text-danger p-3 mb-0">Failed to load channels</p>');
        });
    }
    page(0);
}

function renderAssignList() {
    const q = ($('#channelFilter').val() || '').toLowerCase().trim();
    const catFilter = $('#channelCatFilter').val();
    let rows = allChannels.slice();
    if (q) {
        rows = rows.filter(function(ch) {
            return (ch.channel_name || '').toLowerCase().indexOf(q) >= 0 ||
                (ch.channel_id || '').toLowerCase().indexOf(q) >= 0;
        });
    }
    if (catFilter === '__none__') {
        rows = rows.filter(function(ch) { return !(ch.categories && ch.categories.length); });
    } else if (catFilter) {
        const cid = Number(catFilter);
        rows = rows.filter(function(ch) {
            return (ch.categories || []).some(function(c) { return c.id === cid; });
        });
    }
    if (!rows.length) {
        $('#assignChannelList').html('<p class="text-muted p-3 mb-0">No channels match.</p>');
        updateSelCount();
        return;
    }
    const html = rows.map(function(ch) {
        const cats = (ch.categories || []).map(function(c) {
            return '<span class="badge bg-light text-dark border me-1">' + esc(c.name_zh || c.slug) + '</span>';
        }).join('') || '<span class="text-muted small">Uncategorized</span>';
        const checked = selectedIds.has(ch.id) ? ' checked' : '';
        const thumb = ch.thumbnail_url || 'https://www.gstatic.com/youtube/img/branding/youtubelogo/svg/youtubelogo.svg';
        return '<label class="d-flex align-items-center gap-2 px-3 py-2 border-bottom mb-0 assign-row" style="cursor:pointer">' +
            '<input type="checkbox" class="form-check-input ch-check" value="' + ch.id + '"' + checked +
            ' onchange="toggleSel(' + ch.id + ', this.checked)">' +
            '<img src="' + esc(thumb) + '" alt="" width="32" height="32" class="rounded-circle" style="object-fit:cover" onerror="this.style.display=\'none\'">' +
            '<div class="flex-grow-1"><div class="fw-semibold">' + esc(ch.channel_name) + '</div>' +
            '<div class="small">' + cats + '</div></div>' +
            '<span class="badge ' + (ch.crawl_enabled ? 'bg-success' : 'bg-secondary') + '">' +
            (ch.crawl_enabled ? 'On' : 'Off') + '</span></label>';
    }).join('');
    $('#assignChannelList').html(html);
    updateSelCount();
}

function toggleSel(id, on) {
    if (on) selectedIds.add(id); else selectedIds.delete(id);
    updateSelCount();
}

function updateSelCount() {
    $('#channelSelCount').text(selectedIds.size + ' selected');
}

function openCreateCategory() {
    $('#categoryModalTitle').text('New category');
    $('#editCatId').val('');
    $('#catNameZh').val('');
    $('#catNameEn').val('');
    $('#catSlug').val('');
    $('#catSort').val('');
}

function openEditCategory(id) {
    const cats = (statsCache && statsCache.by_category) || [];
    const c = cats.find(function(x) { return x.id === id; });
    if (!c) return;
    $('#categoryModalTitle').text('Edit category');
    $('#editCatId').val(c.id);
    $('#catNameZh').val(c.name_zh || '');
    $('#catNameEn').val(c.name_en || '');
    $('#catSlug').val(c.slug || '');
    $('#catSort').val(c.sort_order);
    new bootstrap.Modal(document.getElementById('categoryModal')).show();
}

function saveCategory() {
    const id = $('#editCatId').val();
    const payload = {
        name_zh: $('#catNameZh').val().trim(),
        name_en: $('#catNameEn').val().trim(),
    };
    const slug = $('#catSlug').val().trim();
    const sort = $('#catSort').val();
    if (!payload.name_zh || !payload.name_en) {
        alert('Chinese and English names are required');
        return;
    }
    if (slug) payload.slug = slug;
    if (sort !== '') payload.sort_order = Number(sort);

    const req = id
        ? $.ajax({ url: '/api/categories/' + id, method: 'PUT', contentType: 'application/json', data: JSON.stringify(payload) })
        : $.ajax({ url: '/api/categories/', method: 'POST', contentType: 'application/json', data: JSON.stringify(payload) });

    req.done(function() {
        bootstrap.Modal.getInstance(document.getElementById('categoryModal')).hide();
        refreshAll();
    }).fail(function(xhr) {
        if (xhr.status === 401) { redirectToLogin(); return; }
        alert('Save failed: ' + (xhr.responseJSON && xhr.responseJSON.detail || xhr.statusText));
    });
}

function deleteCategory(id, slug) {
    if (!confirm('Delete category "' + slug + '"? Channels keep other categories; this membership is removed.')) return;
    $.ajax({ url: '/api/categories/' + id, method: 'DELETE' })
        .done(function() {
            if (manageCatId === id) {
                manageCatId = null;
                $('#manageCategorySelect').val('');
                onManageCategoryChange();
            }
            refreshAll();
        })
        .fail(function(xhr) {
            if (xhr.status === 401) { redirectToLogin(); return; }
            alert('Delete failed: ' + (xhr.responseJSON && xhr.responseJSON.detail || xhr.statusText));
        });
}

function assignSelected() {
    const catId = $('#assignCategorySelect').val();
    if (!catId) { alert('Pick a category'); return; }
    const ids = Array.from(selectedIds);
    if (!ids.length) { alert('Select one or more channels'); return; }
    $.ajax({
        url: '/api/categories/' + catId + '/assign',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ channel_ids: ids })
    }).done(function() {
        selectedIds.clear();
        refreshAll();
    }).fail(function(xhr) {
        if (xhr.status === 401) { redirectToLogin(); return; }
        alert('Assign failed: ' + (xhr.responseJSON && xhr.responseJSON.detail || xhr.statusText));
    });
}

function unassignSelected() {
    const catId = $('#assignCategorySelect').val();
    if (!catId) { alert('Pick a category'); return; }
    const ids = Array.from(selectedIds);
    if (!ids.length) { alert('Select one or more channels'); return; }
    $.ajax({
        url: '/api/categories/' + catId + '/unassign',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ channel_ids: ids })
    }).done(function() {
        selectedIds.clear();
        refreshAll();
    }).fail(function(xhr) {
        if (xhr.status === 401) { redirectToLogin(); return; }
        alert('Unassign failed: ' + (xhr.responseJSON && xhr.responseJSON.detail || xhr.statusText));
    });
}

// ----- Page-level Add channel (auto-detect categories + manual confirm) -----

let acPreview = null; // last preview response
let acSuggestedIds = new Set();

function openAddChannelModal() {
    acPreview = null;
    acSuggestedIds = new Set();
    $('#acYtSearchQuery').val('');
    $('#acYtSearchResults').empty();
    $('#acChannelUrl').val('').removeData('yt-id');
    $('#acFallbackName').val('');
    $('#acFallbackNameWrap').hide();
    $('#acPreviewBox').hide();
    $('#acPreviewWarning').hide().text('');
    $('#acCategoryChecklist').html('<p class="text-muted small mb-0">Preview a channel to load category suggestions.</p>');
    $('#acSuggestMeta').text('');
    $('#acCrawlFrequency').val('manual');
    $('#acCrawlEnabled').prop('checked', true);
    $('#btnAcSave').prop('disabled', true);
    renderAcCategoryChecklist([]);
    new bootstrap.Modal(document.getElementById('addChannelModal')).show();
}

function renderAcCategoryChecklist(precheckedIds) {
    const cats = (statsCache && statsCache.by_category) || [];
    const pre = new Set((precheckedIds || []).map(Number));
    acSuggestedIds = new Set(pre);
    if (!cats.length) {
        $('#acCategoryChecklist').html('<p class="text-muted small mb-0">No categories loaded. Refresh the page.</p>');
        return;
    }
    const html = cats.map(function(c) {
        const checked = pre.has(c.id) ? ' checked' : '';
        const suggested = pre.has(c.id)
            ? ' <span class="badge bg-info-subtle text-info-emphasis border">auto</span>'
            : '';
        return '<div class="form-check">' +
            '<input class="form-check-input ac-cat-check" type="checkbox" value="' + c.id + '" id="acCat' + c.id + '"' + checked + '>' +
            '<label class="form-check-label" for="acCat' + c.id + '">' +
            esc(c.name_zh || c.slug) +
            ' <span class="text-muted small">(' + esc(c.name_en || c.slug) + ')</span>' +
            suggested +
            '</label></div>';
    }).join('');
    $('#acCategoryChecklist').html(html);
}

function acSelectedCategoryIds() {
    const ids = [];
    $('#acCategoryChecklist .ac-cat-check:checked').each(function() {
        ids.push(String($(this).val()));
    });
    return ids;
}

function acSearchYt() {
    const query = ($('#acYtSearchQuery').val() || '').trim();
    if (query.length < 2) { alert('Enter at least 2 characters'); return; }
    const $r = $('#acYtSearchResults');
    $r.html('<p class="text-muted mb-0"><span class="spinner-border spinner-border-sm me-1"></span>Searching…</p>');
    $.ajax({
        url: '/api/channels/search/youtube?q=' + encodeURIComponent(query) + '&limit=10',
        method: 'GET',
        timeout: 30000
    }).done(function(results) {
        if (!results || !results.length) {
            $r.html('<div class="alert alert-warning mb-0">No channels found. Try a UC… id /channel/ URL if quota is tight.</div>');
            return;
        }
        const $list = $('<div class="list-group"></div>');
        results.forEach(function(ch) {
            const badge = ch.already_added
                ? '<span class="badge bg-secondary">Already in crawler</span>'
                : '<span class="badge bg-success">New</span>';
            const thumb = ch.thumbnail || ch.thumbnail_url || '';
            const url = ch.channel_url || ('https://www.youtube.com/channel/' + (ch.youtube_channel_id || ''));
            const $btn = $('<button type="button" class="list-group-item list-group-item-action d-flex align-items-center gap-2"></button>');
            $btn.on('click', function() {
                $('#acChannelUrl').val(url).data('yt-id', ch.youtube_channel_id || '');
                if (ch.channel_name) $('#acFallbackName').val(ch.channel_name);
                acPreviewChannel();
            });
            let inner = '';
            if (thumb) inner += '<img src="' + esc(thumb) + '" width="40" height="40" class="rounded-circle">';
            inner += '<div class="flex-grow-1 text-start"><div class="fw-semibold">' + esc(ch.channel_name || ch.title || '') + '</div>' +
                '<div class="small text-muted">' + esc(ch.youtube_channel_id || '') + '</div></div>' + badge;
            $btn.html(inner);
            $list.append($btn);
        });
        $r.empty().append($list);
    }).fail(function(xhr) {
        const detail = (xhr.responseJSON && xhr.responseJSON.detail) || xhr.statusText;
        $r.html('<div class="alert alert-danger mb-0">Search failed: ' + esc(detail) +
            '. Paste a /channel/UCxxx URL or UC id instead.</div>');
    });
}

function acPreviewChannel() {
    const url = ($('#acChannelUrl').val() || '').trim();
    const ytFromData = $('#acChannelUrl').data('yt-id');
    const fallback = ($('#acFallbackName').val() || '').trim();
    if (!url && !ytFromData) {
        alert('Paste a YouTube URL / UC id, or pick a search result');
        return;
    }
    const payload = {};
    if (ytFromData) payload.youtube_channel_id = ytFromData;
    if (url) payload.url = url;
    if (fallback) payload.channel_name = fallback;

    $('#acPreviewBox').show();
    $('#acPreviewName').text('Resolving…');
    $('#acPreviewYtId').text('');
    $('#acPreviewMeta').text('');
    $('#acPreviewWarning').hide().text('');
    $('#btnAcSave').prop('disabled', true);

    $.ajax({
        url: '/api/channels/preview',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(payload),
        timeout: 60000
    }).done(function(p) {
        acPreview = p;
        if (p.youtube_channel_id) {
            $('#acChannelUrl').data('yt-id', p.youtube_channel_id);
        }
        $('#acPreviewName').text(p.channel_name || '(name unknown — set display name below)');
        $('#acPreviewYtId').text(p.youtube_channel_id || '');
        let meta = '';
        if (p.already_added) {
            meta = '<span class="badge bg-secondary me-1">Already in crawler</span>';
            if (p.existing_categories && p.existing_categories.length) {
                meta += ' currently: ' + p.existing_categories.map(function(c) {
                    return esc(c.name_zh || c.slug);
                }).join(', ');
            }
        } else {
            meta = '<span class="badge bg-success">New</span> via ' + esc(p.resolved_via || '');
        }
        $('#acPreviewMeta').html(meta);
        if (p.thumbnail_url) {
            $('#acPreviewThumb').attr('src', p.thumbnail_url).show();
        } else {
            $('#acPreviewThumb').hide();
        }
        if (p.warning || !p.channel_name) {
            $('#acFallbackNameWrap').show();
            if (p.warning) {
                $('#acPreviewWarning').text(p.warning).show();
            }
        } else {
            $('#acFallbackNameWrap').hide();
        }
        if (p.channel_name && !$('#acFallbackName').val()) {
            $('#acFallbackName').val(p.channel_name);
        }
        const suggested = p.suggested_category_ids || (p.suggestions || []).map(function(s) { return s.id; });
        renderAcCategoryChecklist(suggested);
        const reasons = (p.suggestions || []).map(function(s) {
            return (s.name_zh || s.slug) + ': ' + (s.reason || '');
        }).join(' · ');
        $('#acSuggestMeta').text(
            suggested.length
                ? ('Auto-detected ' + suggested.length + ' categor' + (suggested.length === 1 ? 'y' : 'ies') +
                   (reasons ? ' — ' + reasons : '') + '. Uncheck / check to change before save.')
                : 'No auto-detect match — pick categories manually.'
        );
        $('#btnAcSave').prop('disabled', !(p.youtube_channel_id || p.existing_channel_id || url));
    }).fail(function(xhr) {
        acPreview = null;
        const detail = (xhr.responseJSON && xhr.responseJSON.detail) || xhr.statusText;
        $('#acPreviewName').text('Preview failed');
        $('#acPreviewWarning').text(detail).show();
        $('#acFallbackNameWrap').show();
        // Still allow save with UC id + manual categories if URL looks like UC
        const uc = (url.match(/UC[\w-]{20,}/) || [])[0];
        if (uc) {
            $('#acChannelUrl').data('yt-id', uc);
            renderAcCategoryChecklist([]);
            $('#btnAcSave').prop('disabled', false);
            $('#acSuggestMeta').text('Preview failed — you can still save with UC id and manual categories.');
            acRefreshSuggest();
        }
    });
}

function acRefreshSuggest() {
    const name = ($('#acFallbackName').val() || (acPreview && acPreview.channel_name) || '').trim();
    const yt = $('#acChannelUrl').data('yt-id') || (acPreview && acPreview.youtube_channel_id) || '';
    const payload = { channel_name: name || undefined, youtube_channel_id: yt || undefined, limit: 5 };
    if (!payload.channel_name && !payload.youtube_channel_id) {
        alert('Preview a channel or enter a display name first');
        return;
    }
    $('#acSuggestMeta').text('Detecting…');
    $.ajax({
        url: '/api/channels/suggest-categories',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(payload)
    }).done(function(res) {
        const ids = res.category_ids || [];
        // Keep currently checked, then ensure suggestions are checked
        const current = new Set(acSelectedCategoryIds().map(Number));
        ids.forEach(function(id) { current.add(Number(id)); });
        renderAcCategoryChecklist(Array.from(current));
        // Re-check only union: renderAc already checks pre list
        const reasons = (res.suggestions || []).map(function(s) {
            return (s.name_zh || s.slug) + ': ' + (s.reason || '');
        }).join(' · ');
        $('#acSuggestMeta').text(
            ids.length
                ? ('Auto-detected via ' + (res.methods || []).join('+') +
                   (reasons ? ' — ' + reasons : ''))
                : 'No suggestions — pick manually.'
        );
    }).fail(function(xhr) {
        $('#acSuggestMeta').text('Auto-detect failed: ' +
            ((xhr.responseJSON && xhr.responseJSON.detail) || xhr.statusText));
    });
}

function acSaveChannel() {
    const url = ($('#acChannelUrl').val() || '').trim();
    const ytId = $('#acChannelUrl').data('yt-id') || (acPreview && acPreview.youtube_channel_id) || null;
    const fallback = ($('#acFallbackName').val() || '').trim();
    const categoryIds = acSelectedCategoryIds();

    if (!url && !ytId && !(acPreview && acPreview.existing_channel_id)) {
        alert('Need a YouTube URL, UC id, or previewed channel');
        return;
    }

    const payload = {
        crawl_enabled: $('#acCrawlEnabled').is(':checked'),
        crawl_frequency: $('#acCrawlFrequency').val() || 'manual',
        category_ids: categoryIds,
    };
    if (acPreview && acPreview.existing_channel_id) {
        payload.channel_id = acPreview.existing_channel_id;
    } else if (ytId) {
        payload.youtube_channel_id = ytId;
        if (url) payload.url = url;
    } else {
        payload.url = url;
    }
    if (fallback) payload.channel_name = fallback;

    const $btn = $('#btnAcSave');
    const original = $btn.text();
    $btn.text('Saving…').prop('disabled', true);

    $.ajax({
        url: '/api/channels/add-with-categories',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(payload),
        timeout: 90000
    }).done(function(ch) {
        $btn.text(original).prop('disabled', false);
        bootstrap.Modal.getInstance(document.getElementById('addChannelModal')).hide();
        const catNames = (ch.categories || []).map(function(c) { return c.name_zh || c.slug; }).join(', ') || 'none';
        alert('Saved: ' + (ch.channel_name || ch.channel_id) + '\nCategories: ' + catNames);
        refreshAll();
    }).fail(function(xhr) {
        $btn.text(original).prop('disabled', false);
        if (xhr.status === 401) { redirectToLogin(); return; }
        alert('Save failed: ' + ((xhr.responseJSON && xhr.responseJSON.detail) || xhr.statusText));
    });
}

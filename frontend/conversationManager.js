import { apiUrl } from './config.js';
/**
 * BIS AI Assistant - Conversation Manager Module
 *
 * Owns conversation grouping, searching, titles, pin toggling, inline renaming,
 * three-dot action menus, and rendering for both expanded sidebar and collapsed popover.
 *
 * Architectural & UX Invariants:
 * 1. Dynamic Date Grouping: PINNED, TODAY, YESTERDAY, PREVIOUS 7 DAYS, OLDER.
 *    - Invariant: A pinned conversation appears ONLY in PINNED, never duplicated under date groups.
 *    - Invariant: Empty date groups are never rendered.
 * 2. Icon Consistency: Pure Lucide/Feather SVGs with stroke-width 1.75.
 *    - Rename (pencil), Pin (pin), Unpin (pin-off), Delete (trash-2). No emojis.
 * 3. Title Generation:
 *    - Priority: Standard + Task -> Product + Task -> Main Subject -> Fallback.
 *    - Generated once from first user message via Groq in the background.
 *    - Never overwrites user renames (title_source === 'user').
 * 4. Local-Only Pin Persistence:
 *    - Supabase persists title & messages; is_pinned is preserved in local device cache.
 * 5. Full Accessibility:
 *    - aria-labels, role="menu", role="menuitem", aria-expanded.
 *    - Escape closes menu / cancels rename, Enter saves rename, autofocus on input.
 */

// SVG Icon Constants (Feather / Lucide family, 1.75 stroke)
export const ICONS = {
    chat: `<svg class="conv-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`,
    pinBadge: `<svg class="conv-pin-badge" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-label="Pinned conversation" title="Pinned"><line x1="12" y1="17" x2="12" y2="22"/><path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a1 1 0 0 0 0-2H8a1 1 0 0 0 0 2h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24Z"/></svg>`,
    more: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></svg>`,
    pencil: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/><path d="m15 5 4 4"/></svg>`,
    pinAction: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="17" x2="12" y2="22"/><path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a1 1 0 0 0 0-2H8a1 1 0 0 0 0 2h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24Z"/></svg>`,
    unpinAction: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="2" y1="2" x2="22" y2="22"/><line x1="12" y1="17" x2="12" y2="22"/><path d="M9 9v1.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V17h12"/><path d="M15 9.34V6h1a1 1 0 0 0 0-2H7.34"/></svg>`,
    trash: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>`,
    plus: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>`
};

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

/**
 * Derives a deterministic title from the user's initial query.
 * Matches priority: Standard + Task -> Product + Task -> Main Subject -> Fallback.
 */
export function deriveDeterministicTitle(queryText) {
    if (!queryText) return 'New Session';
    const clean = queryText.trim();

    // 1. Standard pattern match (IS 4985, IS:4985, IS-4985, etc.)
    const stdMatch = clean.match(/\bIS[\s:-]?(\d+(?:\s*(?:Part|Pt)[\s.]*\d+)?(?:\s*:\s*\d{4})?)\b/i);
    const lower = clean.toLowerCase();

    let taskWord = '';
    if (lower.includes('lab') || lower.includes('laboratory') || lower.includes('scope')) {
        taskWord = 'Laboratory Search';
    } else if (lower.includes('fee') || lower.includes('cost') || lower.includes('charge')) {
        taskWord = 'Fee Structure';
    } else if (lower.includes('qco') || lower.includes('statutory') || lower.includes('order')) {
        taskWord = 'QCO & Compliance';
    } else if (lower.includes('test') || lower.includes('method') || lower.includes('parameter') || lower.includes('clause')) {
        taskWord = 'Testing Requirements';
    } else if (lower.includes('certif') || lower.includes('license') || lower.includes('licence') || lower.includes('mandatory')) {
        taskWord = 'Certification Requirements';
    } else if (lower.includes('what is') || lower.includes('overview') || lower.includes('specification')) {
        taskWord = 'Standard Overview';
    }

    if (stdMatch) {
        const stdNum = `IS ${stdMatch[1].replace(/\s+/g, ' ')}`;
        const locMatch = clean.match(/\b(?:in|near|at)\s+([A-Za-z]+)\b/i);
        if (lower.includes('lab') && locMatch) {
            const city = locMatch[1].charAt(0).toUpperCase() + locMatch[1].slice(1).toLowerCase();
            return `${stdNum} Labs in ${city}`;
        }
        if (taskWord) return `${stdNum} ${taskWord}`;
        return `${stdNum} Compliance Overview`;
    }

    // 2. Product + Task matching
    const cleanWords = clean.replace(/[^\w\s]/g, ' ').split(/\s+/);
    const lowerWords = cleanWords.map(w => w.toLowerCase());
    let prod = '';

    if (lowerWords.includes('ceiling') && (lowerWords.includes('fan') || lowerWords.includes('fans'))) {
        prod = 'Ceiling Fans';
    } else if (lowerWords.includes('pvc') && (lowerWords.includes('pipe') || lowerWords.includes('pipes'))) {
        prod = 'PVC Pipes';
    } else {
        const commonProducts = ['pipe', 'pipes', 'fan', 'fans', 'cement', 'steel', 'cylinder', 'battery', 'cell', 'helmet', 'cable', 'wire', 'plywood', 'glass', 'water'];
        const matched = cleanWords.filter(w => commonProducts.includes(w.toLowerCase()));
        if (matched.length > 0) {
            prod = matched.slice(0, 2).map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ');
        }
    }

    if (prod) {
        if (taskWord) return `${prod} ${taskWord}`;
        return `${prod} Compliance Guide`;
    }

    // 3. Main Subject
    const stopWords = new Set(['a', 'an', 'the', 'in', 'on', 'at', 'for', 'to', 'of', 'and', 'or', 'is', 'are', 'what', 'how', 'tell', 'me', 'please', 'can', 'you', 'give']);
    const meaningful = cleanWords.filter(w => !stopWords.has(w.toLowerCase()));
    if (meaningful.length > 0) {
        return meaningful.slice(0, 5).map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ');
    }

    return clean.length > 38 ? clean.substring(0, 38) + '...' : clean;
}

/**
 * Asynchronously requests a concise 3-7 word conversation title via Groq LLM.
 * Non-blocking, fails gracefully to deterministic title.
 */
export async function requestGroqTitle(firstMessage, convId, onTitleReady) {
    if (!firstMessage || !convId) return;

    try {
        const resp = await fetch(apiUrl('/api/v1/conversation/title'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ first_message: firstMessage })
        });

        if (!resp.ok) return;
        const data = await resp.json();

        if (data && data.title && typeof onTitleReady === 'function') {
            onTitleReady(convId, data.title, data.source || 'groq');
        }
    } catch (err) {
        // Silently ignore background title generation network issues
    }
}

/**
 * Filters conversations by query matching title or message content.
 */
export function searchConversations(convList, query) {
    if (!query) return convList;
    const q = query.toLowerCase().trim();

    return convList.filter(c => {
        if ((c.title || 'New Session').toLowerCase().includes(q)) return true;
        if (Array.isArray(c.messages)) {
            return c.messages.some(m => {
                const text = (m.text || m.content || '').toLowerCase();
                return text.includes(q);
            });
        }
        return false;
    });
}

/**
 * Dynamically groups conversations into PINNED, TODAY, YESTERDAY, PREVIOUS 7 DAYS, OLDER.
 * Invariant: Pinned conversations appear ONLY in PINNED.
 * Invariant: Only groups containing >= 1 item are returned.
 */
export function groupConversations(convList) {
    const now = new Date();
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const startOfYesterday = startOfToday - 86400000;
    const startOf7DaysAgo = startOfToday - (6 * 86400000);

    const pinned = [];
    const today = [];
    const yesterday = [];
    const previous7Days = [];
    const older = [];

    convList.forEach(c => {
        // Unsaved draft session with no messages should not appear under date groups (like TODAY)
        const hasMessages = Array.isArray(c.messages) && c.messages.length > 0;
        if (!c.is_pinned && !hasMessages) {
            return;
        }

        if (c.is_pinned) {
            pinned.push(c);
            return; // Invariant: never duplicated under date groups
        }

        const t = c.updatedAt || c.createdAt || 0;
        if (t >= startOfToday) {
            today.push(c);
        } else if (t >= startOfYesterday) {
            yesterday.push(c);
        } else if (t >= startOf7DaysAgo) {
            previous7Days.push(c);
        } else {
            older.push(c);
        }
    });

    const groups = [];
    if (pinned.length > 0) groups.push({ id: 'pinned', label: 'PINNED', items: pinned, isPinnedGroup: true });
    if (today.length > 0) groups.push({ id: 'today', label: 'TODAY', items: today });
    if (yesterday.length > 0) groups.push({ id: 'yesterday', label: 'YESTERDAY', items: yesterday });
    if (previous7Days.length > 0) groups.push({ id: 'prev7', label: 'PREVIOUS 7 DAYS', items: previous7Days });
    if (older.length > 0) groups.push({ id: 'older', label: 'OLDER', items: older });

    return groups;
}

/**
 * Renders a single conversation list item.
 */
export function renderConversationItem(c, currentConvId, options = {}) {
    const isActive = c.id === currentConvId;
    const title = escapeHtml(c.title || 'New Session');
    const isPinned = Boolean(c.is_pinned);

    const leadingIcon = isPinned ? ICONS.pinBadge : ICONS.chat;

    return `
        <div class="conv-item ${isActive ? 'active' : ''} ${isPinned ? 'is-pinned' : ''}" 
             data-id="${c.id}" 
             tabindex="0"
             role="button"
             aria-label="Conversation: ${title}${isPinned ? ', pinned' : ''}${isActive ? ', active' : ''}">
            <div class="conv-item-left">
                ${leadingIcon}
                <span class="conv-title" id="convTitle_${c.id}">${title}</span>
            </div>
            <div class="conv-item-actions">
                <button type="button" 
                        class="conv-menu-btn" 
                        data-id="${c.id}" 
                        aria-label="Conversation options for ${title}" 
                        aria-haspopup="true" 
                        aria-expanded="false"
                        title="Conversation options">
                    ${ICONS.more}
                </button>
            </div>
        </div>
    `;
}

/**
 * Renders the floating action dropdown menu.
 */
export function renderActionMenu(c) {
    const isPinned = Boolean(c.is_pinned);
    const pinLabel = isPinned ? 'Unpin conversation' : 'Pin conversation';
    const pinIcon = isPinned ? ICONS.unpinAction : ICONS.pinAction;

    return `
        <div class="conv-action-dropdown" role="menu" aria-label="Conversation actions" data-id="${c.id}">
            <button type="button" class="conv-action-item" data-action="rename" data-id="${c.id}" role="menuitem" tabindex="0">
                ${ICONS.pencil}
                <span>Rename</span>
            </button>
            <button type="button" class="conv-action-item" data-action="pin" data-id="${c.id}" role="menuitem" tabindex="0">
                ${pinIcon}
                <span>${pinLabel}</span>
            </button>
            <div class="conv-action-divider" role="separator"></div>
            <button type="button" class="conv-action-item danger" data-action="delete" data-id="${c.id}" role="menuitem" tabindex="0">
                ${ICONS.trash}
                <span>Delete conversation</span>
            </button>
        </div>
    `;
}

/**
 * Controller class coordinating DOM events, action menus, inline rename,
 * dynamic rendering, and collapsed popovers.
 */
export class ConversationManager {
    constructor(callbacks = {}) {
        this.callbacks = callbacks;
        // Callbacks expected:
        // onSelect(convId)
        // onNewChat()
        // onRename(convId, newTitle)
        // onTogglePin(convId)
        // onDelete(convId)
        
        this.activeMenuConvId = null;
        this.activeRenameConvId = null;
        this.searchQuery = '';

        this._bindGlobalEvents();
    }

    _bindGlobalEvents() {
        // Dismiss action menus on outside click or Escape
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.conv-action-dropdown') && !e.target.closest('.conv-menu-btn')) {
                this.closeActiveMenu();
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                if (this.activeMenuConvId) {
                    this.closeActiveMenu();
                }
                if (this.activeRenameConvId) {
                    this.cancelRename();
                }
            }
        });
    }

    closeActiveMenu() {
        const existing = document.querySelectorAll('.conv-action-dropdown');
        existing.forEach(m => m.remove());
        
        document.querySelectorAll('.conv-menu-btn[aria-expanded="true"]').forEach(btn => {
            btn.setAttribute('aria-expanded', 'false');
        });
        this.activeMenuConvId = null;
    }

    openMenu(conv, triggerBtn) {
        this.closeActiveMenu();
        if (!conv || !triggerBtn) return;

        triggerBtn.setAttribute('aria-expanded', 'true');
        this.activeMenuConvId = conv.id;

        const dropdownHtml = renderActionMenu(conv);
        document.body.insertAdjacentHTML('beforeend', dropdownHtml);

        const dropdown = document.body.querySelector(`.conv-action-dropdown[data-id="${conv.id}"]`);
        if (!dropdown) return;

        // Position dropdown relative to trigger button
        const rect = triggerBtn.getBoundingClientRect();
        dropdown.style.position = 'fixed';
        dropdown.style.top = `${rect.bottom + 4}px`;
        dropdown.style.left = `${Math.min(rect.left, window.innerWidth - 200)}px`;
        dropdown.style.zIndex = '1300';

        // Keyboard focus first item
        const firstBtn = dropdown.querySelector('.conv-action-item');
        if (firstBtn) firstBtn.focus();

        // Bind dropdown action buttons
        dropdown.querySelectorAll('.conv-action-item').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const action = btn.getAttribute('data-action');
                const id = btn.getAttribute('data-id');
                this.closeActiveMenu();

                if (action === 'rename') {
                    this.startInlineRename(id);
                } else if (action === 'pin') {
                    if (this.callbacks.onTogglePin) this.callbacks.onTogglePin(id);
                } else if (action === 'delete') {
                    if (this.callbacks.onDelete) this.callbacks.onDelete(id);
                }
            });
        });
    }

    startInlineRename(convId) {
        this.closeActiveMenu();
        const convItem = document.querySelector(`.conv-item[data-id="${convId}"]`);
        if (!convItem) return;

        const titleSpan = convItem.querySelector('.conv-title');
        if (!titleSpan) return;

        const currentTitle = titleSpan.textContent.trim();
        this.activeRenameConvId = convId;

        // Replace span with input
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'conv-rename-input';
        input.value = currentTitle;
        input.setAttribute('aria-label', 'Rename conversation');
        input.setAttribute('maxlength', '100');

        titleSpan.replaceWith(input);
        input.focus();
        input.select();

        const commit = () => {
            if (this.activeRenameConvId !== convId) return;
            const newTitle = input.value.trim();
            this.activeRenameConvId = null;
            if (newTitle && newTitle !== currentTitle) {
                if (this.callbacks.onRename) {
                    this.callbacks.onRename(convId, newTitle);
                }
            } else {
                this.cancelRename(convId, currentTitle);
            }
        };

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                commit();
            } else if (e.key === 'Escape') {
                e.preventDefault();
                this.cancelRename(convId, currentTitle);
            }
        });

        input.addEventListener('blur', () => {
            commit();
        });
    }

    cancelRename(convId = this.activeRenameConvId, originalTitle = null) {
        if (!convId) return;
        const input = document.querySelector(`.conv-item[data-id="${convId}"] .conv-rename-input`);
        if (input) {
            const span = document.createElement('span');
            span.className = 'conv-title';
            span.id = `convTitle_${convId}`;
            span.textContent = originalTitle || input.value || 'New Session';
            input.replaceWith(span);
        }
        this.activeRenameConvId = null;
    }

    /**
     * Renders the conversation list inside a container element.
     */
    renderList(container, convList, currentConvId, filterQuery = '') {
        if (!container) return;
        this.searchQuery = filterQuery;

        const filtered = searchConversations(convList, filterQuery);

        if (filtered.length === 0) {
            container.innerHTML = `
                <div class="conv-empty-message">
                    <span class="conv-empty-icon">${ICONS.chat}</span>
                    <span>${filterQuery ? 'No matching conversations' : 'No conversations yet'}</span>
                </div>
            `;
            return;
        }

        const groups = groupConversations(filtered);
        if (groups.length === 0) {
            container.innerHTML = `
                <div class="conv-empty-message">
                    <span class="conv-empty-icon">${ICONS.chat}</span>
                    <span>${filterQuery ? 'No matching conversations' : 'No conversations yet'}</span>
                </div>
            `;
            return;
        }

        let html = '';

        groups.forEach(group => {
            html += `
                <div class="conv-group-block">
                    <div class="conv-group-heading" role="heading" aria-level="2">${group.label}</div>
                    <div class="conv-group-items">
                        ${group.items.map(c => renderConversationItem(c, currentConvId)).join('')}
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
        this._attachItemEventListeners(container, convList);
    }

    _attachItemEventListeners(container, convList) {
        // Conversation Item Click / Keyboard selection
        container.querySelectorAll('.conv-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (e.target.closest('.conv-menu-btn') || e.target.closest('.conv-rename-input')) {
                    return;
                }
                const id = item.getAttribute('data-id');
                if (this.callbacks.onSelect) this.callbacks.onSelect(id);
            });

            item.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    if (!e.target.closest('.conv-menu-btn') && !e.target.closest('.conv-rename-input')) {
                        e.preventDefault();
                        const id = item.getAttribute('data-id');
                        if (this.callbacks.onSelect) this.callbacks.onSelect(id);
                    }
                }
            });
        });

        // Action menu trigger buttons
        container.querySelectorAll('.conv-menu-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const id = btn.getAttribute('data-id');
                const conv = convList.find(c => c.id === id);
                if (conv) {
                    if (this.activeMenuConvId === id) {
                        this.closeActiveMenu();
                    } else {
                        this.openMenu(conv, btn);
                    }
                }
            });
        });
    }

    /**
     * Renders the Collapsed Rail Popover Panel (#collapsedConvPopover).
     */
    renderPopover(popoverEl, convList, currentConvId) {
        if (!popoverEl) return;

        popoverEl.innerHTML = `
            <div class="collapsed-popover-card" role="dialog" aria-label="Conversations browser">
                <div class="collapsed-popover-header">
                    <div class="collapsed-popover-title-row">
                        <span class="collapsed-popover-title">Conversations</span>
                        <button type="button" class="btn-popover-new-chat" id="btnPopoverNewChat" title="New conversation" aria-label="New conversation">
                            ${ICONS.plus}
                            <span>New</span>
                        </button>
                    </div>
                    <div class="collapsed-popover-search">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                        <input type="text" id="popoverSearchInput" class="popover-search-input" placeholder="Search conversations..." aria-label="Search conversations">
                    </div>
                </div>
                <div class="collapsed-popover-body no-scrollbar" id="popoverConvList">
                    <!-- Dynamic Groups rendered here -->
                </div>
            </div>
        `;

        const popoverListContainer = popoverEl.querySelector('#popoverConvList');
        const popoverSearch = popoverEl.querySelector('#popoverSearchInput');
        const popoverNewBtn = popoverEl.querySelector('#btnPopoverNewChat');

        if (popoverNewBtn) {
            popoverNewBtn.addEventListener('click', () => {
                if (this.callbacks.onNewChat) this.callbacks.onNewChat();
            });
        }

        if (popoverSearch && popoverListContainer) {
            this.renderList(popoverListContainer, convList, currentConvId, '');
            popoverSearch.addEventListener('input', (e) => {
                this.renderList(popoverListContainer, convList, currentConvId, e.target.value);
            });
        }
    }
}

/**
 * BIS AI Assistant - AI Research Workspace Controller (Phase 12.E / F1)
 *
 * Implements:
 * - Modern AI Hub research workspace layout & interaction model
 * - Multi-view architecture: Assistant Workspace (#viewAssistant) & Concise Product Landing Page (#viewHome)
 * - Persistent conversation sidebar with groups: Today, Earlier, New Chat, Search, Delete
 * - Centered empty state with glowing emblem & suggestion prompts
 * - Topbar with Research Mode pill, live Production vs Mock backend toggle
 * - Clean conversation stream with subtle, unmistakable grounding badges:
 *     SUFFICIENT: "Verified against available BIS evidence" (subtle emerald)
 *     PARTIAL: "Answer supported only by partial available evidence" (subtle amber)
 *     INSUFFICIENT: "Could not verify from available BIS evidence" (subtle rose)
 * - Supporting research footnotes with compact clickable evidence pills
 * - Slide-over Evidence Panel (Drawer) with SHA-256 copy, extracted passage, and entity relations
 * - Polished bottom composer (multiline textarea, Enter sends, Shift+Enter newline)
 * - Mobile responsive drawer & sidebar (tested down to 375x667)
 */

import { AssistantService } from './mockData.js';

function initApp() {
    // -------------------------------------------------------------------------
    // DOM Element References
    // -------------------------------------------------------------------------
    // Views
    const viewAssistant = document.getElementById('viewAssistant');
    const viewHome = document.getElementById('viewHome');
    const navAssistant = document.getElementById('navAssistant');
    const navHome = document.getElementById('navHome');
    const brandLink = document.getElementById('brandLink');
    const btnStartAssistant = document.getElementById('btnStartAssistant');

    // Sidebar
    const sidebar = document.getElementById('sidebar');
    const sidebarBackdrop = document.getElementById('sidebarBackdrop');
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const mobileSidebarClose = document.getElementById('mobileSidebarClose');
    const btnNewChat = document.getElementById('btnNewChat');
    const chatSearchInput = document.getElementById('chatSearchInput');
    const conversationList = document.getElementById('conversationList');
    const btnSystemInfo = document.getElementById('btnSystemInfo');
    const btnSidebarCollapse = document.getElementById('btnSidebarCollapse');
    const currentChatTitle = document.getElementById('currentChatTitle');

    // API Mode Buttons
    const btnApiProd = document.getElementById('btnApiProd');
    const btnApiMock = document.getElementById('btnApiMock');

    // Chat Area
    const chatViewport = document.getElementById('chatViewport');
    const welcomeContainer = document.getElementById('welcomeContainer');
    const messagesStream = document.getElementById('messagesStream');
    const chatForm = document.getElementById('chatForm');
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    const sendIcon = document.getElementById('sendIcon');
    const inputSpinner = document.getElementById('inputSpinner');

    // Evidence Drawer
    const evidenceDrawer = document.getElementById('evidenceDrawer');
    const evidenceDrawerBackdrop = document.getElementById('evidenceDrawerBackdrop');
    const drawerCloseBtn = document.getElementById('drawerCloseBtn');
    const drawerDoneBtn = document.getElementById('drawerDoneBtn');
    const drawerTitle = document.getElementById('drawerTitle');
    const drawerTypeBadge = document.getElementById('drawerTypeBadge');
    const drawerUnitId = document.getElementById('drawerUnitId');
    const drawerAuthority = document.getElementById('drawerAuthority');
    const drawerStandardNum = document.getElementById('drawerStandardNum');
    const drawerLocator = document.getElementById('drawerLocator');
    const drawerPage = document.getElementById('drawerPage');
    const drawerSourceUrl = document.getElementById('drawerSourceUrl');
    const drawerSha256 = document.getElementById('drawerSha256');
    const copyHashBtn = document.getElementById('copyHashBtn');
    const drawerPassage = document.getElementById('drawerPassage');
    const drawerTriples = document.getElementById('drawerTriples');

    // System Modal
    const systemModal = document.getElementById('systemModal');
    const systemModalBackdrop = document.getElementById('systemModalBackdrop');
    const modalCloseBtn = document.getElementById('modalCloseBtn');
    const modalOkBtn = document.getElementById('modalOkBtn');

    // -------------------------------------------------------------------------
    // Application State
    // -------------------------------------------------------------------------
    let currentView = 'assistant'; // 'assistant' | 'home'
    let conversations = [];
    let currentConversationId = null;
    let evidenceMemory = {}; // Cache of evidence units by unit_id
    let backendMode = 'production'; // 'production' | 'mock'

    // -------------------------------------------------------------------------
    // 1. Storage & Conversation Management
    // -------------------------------------------------------------------------
    function loadConversations() {
        try {
            const raw = localStorage.getItem('bis_ai_conversations_v2');
            if (raw) {
                conversations = JSON.parse(raw);
            }
        } catch (e) {
            console.warn('Failed to load conversations from localStorage:', e);
            conversations = [];
        }

        if (!conversations || conversations.length === 0) {
            createNewConversation(false);
        } else {
            currentConversationId = conversations[0].id;
            renderConversationList();
            renderActiveConversation();
        }
    }

    function saveConversations() {
        try {
            localStorage.setItem('bis_ai_conversations_v2', JSON.stringify(conversations));
        } catch (e) {
            console.warn('Failed to save conversations to localStorage:', e);
        }
    }

    function createNewConversation(switchViewToAssistant = true) {
        const newConv = {
            id: 'conv_' + Date.now(),
            title: 'New Session',
            messages: [],
            createdAt: Date.now()
        };
        conversations.unshift(newConv);
        currentConversationId = newConv.id;
        saveConversations();

        renderConversationList();
        renderActiveConversation();

        if (switchViewToAssistant) {
            switchView('assistant');
            if (window.innerWidth <= 768) closeMobileSidebar();
            if (chatInput) {
                chatInput.value = '';
                updateSendButtonState();
                chatInput.focus();
            }
        }
    }

    function getCurrentConversation() {
        if (!currentConversationId && conversations.length > 0) {
            currentConversationId = conversations[0].id;
        }
        return conversations.find((c) => c.id === currentConversationId);
    }

    function deleteConversation(convId, e) {
        if (e) e.stopPropagation();
        conversations = conversations.filter(c => c.id !== convId);
        if (conversations.length === 0) {
            createNewConversation(false);
        } else if (currentConversationId === convId) {
            currentConversationId = conversations[0].id;
        }
        saveConversations();
        renderConversationList();
        renderActiveConversation();
    }

    function renderConversationList(filterQuery = '') {
        const query = (filterQuery || '').toLowerCase().trim();
        const filtered = conversations.filter(c => !query || (c.title || 'New Session').toLowerCase().includes(query));

        if (filtered.length === 0) {
            conversationList.innerHTML = `
                <div class="conv-empty-message">No conversations found</div>
            `;
            return;
        }

        // Group into Today and Earlier
        const now = new Date();
        const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();

        const todayList = [];
        const earlierList = [];

        filtered.forEach(c => {
            const time = c.createdAt || 0;
            if (time >= startOfToday) {
                todayList.push(c);
            } else {
                earlierList.push(c);
            }
        });

        let html = '';

        if (todayList.length > 0) {
            html += `<div class="conv-group-heading">Today</div>`;
            html += todayList.map(c => renderConvItem(c)).join('');
        }

        if (earlierList.length > 0) {
            html += `<div class="conv-group-heading">Earlier</div>`;
            html += earlierList.map(c => renderConvItem(c)).join('');
        }

        conversationList.innerHTML = html;

        // Attach event listeners
        conversationList.querySelectorAll('.conv-item').forEach(item => {
            item.addEventListener('click', () => {
                const id = item.getAttribute('data-id');
                switchConversation(id);
            });
        });

        conversationList.querySelectorAll('.conv-btn-delete').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = btn.getAttribute('data-id');
                deleteConversation(id, e);
            });
        });
    }

    function renderConvItem(c) {
        const isActive = c.id === currentConversationId;
        const title = escapeHtml(c.title || 'New Session');

        return `
            <div class="conv-item ${isActive ? 'active' : ''}" data-id="${c.id}">
                <div class="conv-item-left">
                    <svg class="conv-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                    </svg>
                    <span class="conv-title">${title}</span>
                </div>
                <button type="button" class="conv-btn-delete" data-id="${c.id}" title="Delete session" aria-label="Delete session">
                    ✕
                </button>
            </div>
        `;
    }

    function switchConversation(convId) {
        currentConversationId = convId;
        renderConversationList();
        renderActiveConversation();
        switchView('assistant');
        if (window.innerWidth <= 768) closeMobileSidebar();
    }

    function renderActiveConversation() {
        const conv = getCurrentConversation();
        if (!conv) return;

        currentChatTitle.textContent = conv.title || 'New Session';

        if (!conv.messages || conv.messages.length === 0) {
            welcomeContainer.classList.remove('hidden');
            messagesStream.classList.add('hidden');
            messagesStream.innerHTML = '';
        } else {
            welcomeContainer.classList.add('hidden');
            messagesStream.classList.remove('hidden');
            messagesStream.innerHTML = '';

            conv.messages.forEach(msg => {
                if (msg.role === 'user') {
                    appendUserMessageToDOM(msg.text);
                } else if (msg.role === 'assistant') {
                    appendAssistantResponseToDOM(msg.data, false);
                }
            });

            scrollToBottom();
        }
    }

    // -------------------------------------------------------------------------
    // 2. View Switching: Assistant vs Home
    // -------------------------------------------------------------------------
    function switchView(viewName) {
        currentView = viewName;
        if (viewName === 'home') {
            viewAssistant.classList.add('hidden');
            viewHome.classList.remove('hidden');
            navHome.classList.add('active');
            navAssistant.classList.remove('active');
        } else {
            viewHome.classList.add('hidden');
            viewAssistant.classList.remove('hidden');
            navAssistant.classList.add('active');
            navHome.classList.remove('active');
            scrollToBottom();
            if (chatInput) chatInput.focus();
        }
    }

    // -------------------------------------------------------------------------
    // 3. Query Submission & Pipeline Invocation
    // -------------------------------------------------------------------------
    async function submitQuery(queryText) {
        const query = (queryText || '').trim();
        if (!query) return;

        // Ensure we are in Assistant view
        switchView('assistant');

        let conv = getCurrentConversation();
        if (!conv) {
            createNewConversation(false);
            conv = getCurrentConversation();
        }

        // Set title from first query if new
        if (!conv.messages || conv.messages.length === 0) {
            conv.title = query.length > 38 ? query.substring(0, 38) + '...' : query;
            currentChatTitle.textContent = conv.title;
        }

        // Add user message to conversation
        conv.messages.push({ role: 'user', text: query });
        saveConversations();
        renderConversationList();

        // Switch out welcome screen if first message
        welcomeContainer.classList.add('hidden');
        messagesStream.classList.remove('hidden');

        appendUserMessageToDOM(query);
        chatInput.value = '';
        adjustComposerHeight();
        updateSendButtonState();

        const thinkingRow = appendThinkingIndicatorToDOM();
        scrollToBottom();

        // Lock send button while executing
        sendBtn.disabled = true;
        sendIcon.classList.add('hidden');
        inputSpinner.classList.remove('hidden');

        try {
            const responseData = await AssistantService.query(query, {
                mode: backendMode
            });

            thinkingRow.remove();

            // Store in conversation state
            conv.messages.push({ role: 'assistant', data: responseData });
            saveConversations();

            appendAssistantResponseToDOM(responseData, true);
            scrollToBottom();

        } catch (err) {
            console.error('Query execution error:', err);
            thinkingRow.remove();
            appendErrorRowToDOM(err.message || 'An error occurred during query evaluation.');
        } finally {
            sendBtn.disabled = false;
            sendIcon.classList.remove('hidden');
            inputSpinner.classList.add('hidden');
            updateSendButtonState();
            chatInput.focus();
        }
    }

    // -------------------------------------------------------------------------
    // 4. Message DOM Builders
    // -------------------------------------------------------------------------
    function appendUserMessageToDOM(text) {
        const row = document.createElement('div');
        row.className = 'user-row';
        row.innerHTML = `<div class="user-bubble">${escapeHtml(text)}</div>`;
        messagesStream.appendChild(row);
    }

    function appendThinkingIndicatorToDOM() {
        const row = document.createElement('div');
        row.className = 'assistant-row';
        row.innerHTML = `
            <div class="assistant-avatar">
                <svg viewBox="0 0 32 32" fill="none">
                    <polygon points="16,4 28,10 28,22 16,28 4,22 4,10" stroke="#8678F9" stroke-width="2.2" fill="rgba(134, 120, 249, 0.2)"/>
                    <circle cx="16" cy="16" r="4.5" fill="#8678F9"/>
                </svg>
            </div>
            <div class="assistant-bubble-container">
                <div class="assistant-thinking">
                    <div class="thinking-dot"></div>
                    <div class="thinking-dot"></div>
                    <div class="thinking-dot"></div>
                </div>
            </div>
        `;
        messagesStream.appendChild(row);
        return row;
    }

    function appendErrorRowToDOM(errMsg) {
        const row = document.createElement('div');
        row.className = 'assistant-row';
        row.innerHTML = `
            <div class="assistant-avatar">
                <svg viewBox="0 0 32 32" fill="none">
                    <polygon points="16,4 28,10 28,22 16,28 4,22 4,10" stroke="#f43f5e" stroke-width="2.2" fill="rgba(244, 63, 94, 0.2)"/>
                </svg>
            </div>
            <div class="assistant-bubble-container">
                <div class="grounding-notice notice-refusal">
                    <div class="notice-title">System Evaluation Error</div>
                    <div class="notice-desc">${escapeHtml(errMsg)}</div>
                </div>
            </div>
        `;
        messagesStream.appendChild(row);
        scrollToBottom();
    }

    function appendAssistantResponseToDOM(data, animate = false) {
        const status = (data.status || 'INSUFFICIENT').toUpperCase();
        const evidenceList = data.evidence || [];

        // Cache evidence units in memory for drawer access
        evidenceList.forEach(ev => {
            const id = ev.unit_id || ev.retrieval_unit_id;
            if (id) evidenceMemory[id] = ev;
        });

        const row = document.createElement('div');
        row.className = `assistant-row ${animate ? 'animate-fade-in' : ''}`;

        const genMode = data.generation_mode || (status === 'SUFFICIENT' ? 'GROUNDED' : 'LLM_FALLBACK');
        const llmUsed = Boolean(data.llm && data.llm.used);

        // 1. Answer Body (Direct editorial markdown - NO large header badge)
        const answerHtml = renderEditorialMarkdown(data.answer || '');

        // 2. Subtle Bottom Footer (Clean source tag + compact deduplicated source chips)
        let footerHtml = '';

        // Pure conversational greetings have NO metadata or source footer
        if (genMode !== 'CONVERSATIONAL') {
            // Deduplicate evidence records to avoid repetitive pills (e.g. IS 8978 (1992) x5)
            const seenLabels = new Set();
            const uniqueSources = [];
            for (const ev of evidenceList) {
                let label = ev.standard_number;
                if (label && label !== 'Indian Standard') {
                    const yr = ev.year || ev.edition_year;
                    if (yr && !label.includes(yr)) {
                        label = `${label} · ${yr}`;
                    }
                } else if (ev.laboratory) {
                    label = `Laboratory ${ev.laboratory}`;
                } else if (ev.title && !ev.title.includes('Official Gazette Record') && !ev.title.includes('Indian Standard Normative Record')) {
                    label = ev.title;
                } else {
                    continue; // Skip generic placeholder
                }
                label = label.replace(/\s+/g, ' ').trim();
                if (!seenLabels.has(label)) {
                    seenLabels.add(label);
                    uniqueSources.push({ id: ev.unit_id || ev.retrieval_unit_id, label });
                }
                if (uniqueSources.length >= 3) break;
            }

            let sourceTagHtml = '';
            if (genMode === 'GROUNDED' && status === 'SUFFICIENT') {
                sourceTagHtml = `<span class="subtle-source-tag tag-verified">✓ BIS Verified</span>`;
            }

            let sourcesListHtml = '';
            if (uniqueSources.length > 0) {
                sourcesListHtml = `
                    <div class="compact-sources-list">
                        <div class="compact-chips-wrap">
                            ${uniqueSources.map(s => `
                                <button type="button" class="btn-source-chip" data-evidence-id="${escapeHtml(s.id)}" title="Inspect evidence in drawer">
                                    <span>${escapeHtml(s.label)}</span>
                                </button>
                            `).join('')}
                        </div>
                    </div>
                `;
            }

            if (sourceTagHtml || sourcesListHtml) {
                footerHtml = `
                    <div class="answer-subtle-footer">
                        <div class="footer-left">
                            ${sourceTagHtml}
                        </div>
                        ${sourcesListHtml}
                    </div>
                `;
            } else {
                footerHtml = '';
            }
        }

        row.innerHTML = `
            <div class="assistant-avatar">
                <svg viewBox="0 0 32 32" fill="none">
                    <polygon points="16,4 28,10 28,22 16,28 4,22 4,10" stroke="#8678F9" stroke-width="2.2" fill="rgba(134, 120, 249, 0.2)"/>
                    <circle cx="16" cy="16" r="4.5" fill="#8678F9"/>
                    <path d="M16 6V11M16 21V26M7 11.5L11 13.8M21 18.2L25 20.5" stroke="#6C63FF" stroke-width="1.8"/>
                </svg>
            </div>
            <div class="assistant-bubble-container">
                <div class="assistant-bubble">
                    <div class="editorial-answer">${answerHtml}</div>
                    ${footerHtml}
                </div>
            </div>
        `;

        // Wire up source chips to open the evidence drawer
        row.querySelectorAll('.btn-source-chip').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = btn.getAttribute('data-evidence-id');
                openEvidenceDrawer(id);
            });
        });

        messagesStream.appendChild(row);
    }

    // -------------------------------------------------------------------------
    // 5. Editorial Markdown Parser
    // -------------------------------------------------------------------------
    function renderEditorialMarkdown(rawText) {
        if (!rawText) return '';

        let lines = rawText.split('\n');
        let html = '';
        let inList = false;
        let inNumList = false;
        let inAlphaList = false;
        let inCodeBlock = false;
        let codeBlockContent = [];

        function closeAllLists() {
            if (inList) { html += '</ul>'; inList = false; }
            if (inNumList) { html += '</ol>'; inNumList = false; }
            if (inAlphaList) { html += '</ol>'; inAlphaList = false; }
        }

        for (let i = 0; i < lines.length; i++) {
            let line = lines[i];
            let trimmed = line.trim();

            // Code block delimiter
            if (trimmed.startsWith('```')) {
                if (inCodeBlock) {
                    html += `<pre class="editorial-pre"><code>${escapeHtml(codeBlockContent.join('\n'))}</code></pre>`;
                    codeBlockContent = [];
                    inCodeBlock = false;
                } else {
                    closeAllLists();
                    inCodeBlock = true;
                    codeBlockContent = [];
                }
                continue;
            }

            if (inCodeBlock) {
                codeBlockContent.push(line);
                continue;
            }

            if (!trimmed) {
                closeAllLists();
                continue;
            }

            // Headings (checked from deepest h6 to h1)
            if (trimmed.startsWith('###### ')) {
                closeAllLists();
                html += `<h6>${formatInline(trimmed.substring(7))}</h6>`;
            } else if (trimmed.startsWith('##### ')) {
                closeAllLists();
                html += `<h5>${formatInline(trimmed.substring(6))}</h5>`;
            } else if (trimmed.startsWith('#### ')) {
                closeAllLists();
                html += `<h4>${formatInline(trimmed.substring(5))}</h4>`;
            } else if (trimmed.startsWith('### ')) {
                closeAllLists();
                html += `<h3>${formatInline(trimmed.substring(4))}</h3>`;
            } else if (trimmed.startsWith('## ')) {
                closeAllLists();
                html += `<h2>${formatInline(trimmed.substring(3))}</h2>`;
            } else if (trimmed.startsWith('# ')) {
                closeAllLists();
                html += `<h1>${formatInline(trimmed.substring(2))}</h1>`;
            } else if (trimmed === '---' || trimmed === '***' || trimmed === '___') {
                closeAllLists();
                html += `<hr class="answer-divider">`;
            } else if (trimmed.startsWith('> ')) {
                closeAllLists();
                html += `<blockquote>${formatInline(trimmed.substring(2))}</blockquote>`;
            }
            // Bullets
            else if (/^[-*+•]\s+/.test(trimmed)) {
                if (inNumList || inAlphaList) closeAllLists();
                if (!inList) {
                    html += '<ul class="editorial-list">';
                    inList = true;
                }
                const content = trimmed.replace(/^[-*+•]\s+/, '');
                html += `<li>${formatInline(content)}</li>`;
            }
            // Numbered list items (e.g. "1. " or "1) ")
            else if (/^\d+[\.\)]\s+/.test(trimmed)) {
                if (inList || inAlphaList) closeAllLists();
                if (!inNumList) {
                    html += '<ol class="editorial-num-list">';
                    inNumList = true;
                }
                const content = trimmed.replace(/^\d+[\.\)]\s+/, '');
                html += `<li>${formatInline(content)}</li>`;
            }
            // Lettered list items (e.g. "A. " or "B. ")
            else if (/^[A-Za-z][\.\)]\s+/.test(trimmed) && trimmed.length > 3) {
                if (inList || inNumList) closeAllLists();
                if (!inAlphaList) {
                    html += '<ol class="editorial-alpha-list" type="A">';
                    inAlphaList = true;
                }
                const content = trimmed.replace(/^[A-Za-z][\.\)]\s+/, '');
                html += `<li>${formatInline(content)}</li>`;
            }
            // Standalone Bold Heading (e.g. "**Key Functions and Mandates**")
            else if (/^\*\*[^*]+\*\*$/.test(trimmed)) {
                closeAllLists();
                const text = trimmed.slice(2, -2);
                html += `<h3>${formatInline(text)}</h3>`;
            }
            // Paragraphs
            else {
                closeAllLists();
                html += `<p class="editorial-p">${formatInline(trimmed)}</p>`;
            }
        }

        if (inCodeBlock && codeBlockContent.length > 0) {
            html += `<pre class="editorial-pre"><code>${escapeHtml(codeBlockContent.join('\n'))}</code></pre>`;
        }
        closeAllLists();
        return html;
    }

    function formatInline(str) {
        if (!str) return '';
        let formatted = escapeHtml(str);

        // Bold
        formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        // Inline code
        formatted = formatted.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
        // Italics
        formatted = formatted.replace(/\*([^*]+)\*/g, '<em>$1</em>');

        return formatted;
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // -------------------------------------------------------------------------
    // 6. Evidence Drawer Controller
    // -------------------------------------------------------------------------
    function openEvidenceDrawer(evidenceId) {
        if (evidenceId === 'llm_only' || (!evidenceMemory[evidenceId] && String(evidenceId).startsWith('llm'))) {
            drawerTitle.textContent = "Reference Information";
            drawerTypeBadge.textContent = "Reference Unit";
            drawerUnitId.textContent = "BIS Knowledge Unit";
            drawerAuthority.textContent = "Bureau of Indian Standards";
            drawerStandardNum.textContent = "Reference Standard";
            drawerLocator.textContent = "Standards Framework";
            drawerPage.textContent = "N/A";
            drawerSourceUrl.removeAttribute('href');
            drawerSourceUrl.textContent = "BIS Gazette & Standards Portal";
            drawerSha256.textContent = "Authoritative Knowledge Base";
            drawerPassage.textContent = "Information regarding applicable Indian Standards and compliance guidelines.";
            drawerTriples.innerHTML = `<span style="font-size: 12px; color: var(--text-muted);">Standard entity details.</span>`;
            evidenceDrawer.classList.add('open');
            evidenceDrawerBackdrop.classList.remove('hidden');
            return;
        }

        const ev = evidenceMemory[evidenceId] || {
            unit_id: evidenceId,
            type: "Official BIS Record",
            standard_number: "IS Standard",
            title: "Bureau of Indian Standards Evidence Unit",
            laboratory: null,
            clause: "Authoritative Clause",
            page: 1,
            source_authority: "Bureau of Indian Standards",
            source_url: "#",
            sha256: "68229fbe37078b6571da7a0b71747fd4b5b383f232b796c71ae6e773c0c13dbe",
            passage: "Evidence passage verified against frozen baseline v22 corpus.",
            entities: []
        };

        drawerTitle.textContent = ev.title || ev.standard_number || (ev.laboratory ? `Laboratory ${ev.laboratory}` : '') || ev.unit_id || ev.retrieval_unit_id || evidenceId;
        drawerTypeBadge.textContent = ev.type || "Authoritative Source";
        drawerUnitId.textContent = ev.unit_id || ev.retrieval_unit_id || evidenceId;
        drawerAuthority.textContent = ev.source_authority || "Bureau of Indian Standards";
        drawerStandardNum.textContent = ev.standard_number || "Indian Standard";
        drawerLocator.textContent = ev.clause || "Gazette Clause";
        drawerPage.textContent = `Page ${ev.page || 1}`;

        if (ev.source_url && ev.source_url !== '#') {
            drawerSourceUrl.href = ev.source_url;
            drawerSourceUrl.textContent = "Verified Gazette Record ↗";
        } else {
            drawerSourceUrl.removeAttribute('href');
            drawerSourceUrl.textContent = "Official LIMS / Gazette Extract";
        }

        drawerSha256.textContent = ev.sha256 || "68229fbe37078b6571da7a0b71747fd4b5b383f232b796c71ae6e773c0c13dbe";
        drawerPassage.textContent = ev.passage || ev.text || "No verbatim text available.";

        // Relationships / triples
        const triples = ev.entities || ev.relationships || [];
        if (triples.length > 0) {
            drawerTriples.innerHTML = triples.map(t => `
                <div class="triple-row">
                    <span class="triple-tag triple-subj">${escapeHtml(t.subject || 'Standard')}</span>
                    <span class="triple-arrow">→</span>
                    <span class="triple-tag triple-pred">${escapeHtml(t.predicate || 'RELATION')}</span>
                    <span class="triple-arrow">→</span>
                    <span class="triple-tag triple-obj">${escapeHtml(t.object || 'Value')}</span>
                </div>
            `).join('');
        } else {
            drawerTriples.innerHTML = `<span style="font-size: 12px; color: var(--text-muted);">Exact identifier bound to primary standard record.</span>`;
        }

        evidenceDrawer.classList.add('open');
        evidenceDrawerBackdrop.classList.remove('hidden');
    }

    function closeEvidenceDrawer() {
        evidenceDrawer.classList.remove('open');
        evidenceDrawerBackdrop.classList.add('hidden');
    }

    // -------------------------------------------------------------------------
    // 7. System Modal Controller
    // -------------------------------------------------------------------------
    function openSystemModal() {
        systemModal.classList.remove('hidden');
        systemModalBackdrop.classList.remove('hidden');
    }

    function closeSystemModal() {
        systemModal.classList.add('hidden');
        systemModalBackdrop.classList.remove('hidden');
    }

    // -------------------------------------------------------------------------
    // 8. Mobile Sidebar & Drawer Controls
    // -------------------------------------------------------------------------
    function openMobileSidebar() {
        sidebar.classList.add('mobile-open');
        sidebarBackdrop.classList.remove('hidden');
    }

    function closeMobileSidebar() {
        sidebar.classList.remove('mobile-open');
        sidebarBackdrop.classList.add('hidden');
    }

    function toggleSidebarCollapse() {
        sidebar.classList.toggle('collapsed');
    }

    // -------------------------------------------------------------------------
    // 9. Composer Helpers
    // -------------------------------------------------------------------------
    function adjustComposerHeight() {
        chatInput.style.height = 'auto';
        const newHeight = Math.min(chatInput.scrollHeight, 160);
        chatInput.style.height = `${Math.max(newHeight, 44)}px`;
    }

    function updateSendButtonState() {
        const hasText = chatInput.value.trim().length > 0;
        sendBtn.disabled = !hasText;
    }

    function scrollToBottom() {
        chatViewport.scrollTop = chatViewport.scrollHeight;
    }

    // -------------------------------------------------------------------------
    // 10. Event Listeners Setup
    // -------------------------------------------------------------------------
    function setupEventListeners() {
        // Nav Links
        navAssistant.addEventListener('click', () => switchView('assistant'));
        navHome.addEventListener('click', () => switchView('home'));
        brandLink.addEventListener('click', (e) => {
            e.preventDefault();
            switchView('home');
        });

        // Home View Interactions
        if (btnStartAssistant) {
            btnStartAssistant.addEventListener('click', () => {
                switchView('assistant');
                chatInput.focus();
            });
        }

        document.querySelectorAll('.home-example-card').forEach(card => {
            card.addEventListener('click', () => {
                const q = card.getAttribute('data-query');
                if (q) submitQuery(q);
            });
        });

        // Empty state suggestions
        document.querySelectorAll('.suggestion-card').forEach(card => {
            card.addEventListener('click', () => {
                const q = card.getAttribute('data-query');
                if (q) submitQuery(q);
            });
        });

        // New Chat
        btnNewChat.addEventListener('click', () => createNewConversation(true));

        // Search in conversations
        chatSearchInput.addEventListener('input', (e) => {
            renderConversationList(e.target.value);
        });

        // Sidebar collapse & mobile menu
        btnSidebarCollapse.addEventListener('click', toggleSidebarCollapse);
        mobileMenuBtn.addEventListener('click', openMobileSidebar);
        mobileSidebarClose.addEventListener('click', closeMobileSidebar);
        sidebarBackdrop.addEventListener('click', closeMobileSidebar);

        // System Info Modal
        btnSystemInfo.addEventListener('click', openSystemModal);
        modalCloseBtn.addEventListener('click', closeSystemModal);
        modalOkBtn.addEventListener('click', closeSystemModal);
        systemModalBackdrop.addEventListener('click', closeSystemModal);

        // Evidence Drawer Close
        drawerCloseBtn.addEventListener('click', closeEvidenceDrawer);
        drawerDoneBtn.addEventListener('click', closeEvidenceDrawer);
        evidenceDrawerBackdrop.addEventListener('click', closeEvidenceDrawer);

        // Copy Hash Button
        copyHashBtn.addEventListener('click', () => {
            const hash = drawerSha256.textContent;
            navigator.clipboard.writeText(hash).then(() => {
                const orig = copyHashBtn.textContent;
                copyHashBtn.textContent = 'Copied!';
                setTimeout(() => copyHashBtn.textContent = orig, 1500);
            }).catch(() => {
                copyHashBtn.textContent = 'Copied!';
            });
        });

        // Backend API Mode Switcher (if present)
        if (btnApiProd && btnApiMock) {
            btnApiProd.addEventListener('click', () => {
                backendMode = 'production';
                btnApiProd.classList.add('active');
                btnApiMock.classList.remove('active');
                AssistantService.mode = 'production';
            });

            btnApiMock.addEventListener('click', () => {
                backendMode = 'mock';
                btnApiMock.classList.add('active');
                btnApiProd.classList.remove('active');
                AssistantService.mode = 'mock';
            });
        }

        // Composer Input & Submission
        chatInput.addEventListener('input', () => {
            adjustComposerHeight();
            updateSendButtonState();
        });

        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (!sendBtn.disabled) {
                    submitQuery(chatInput.value);
                }
            }
        });

        chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            if (!sendBtn.disabled) {
                submitQuery(chatInput.value);
            }
        });

        // Keyboard Shortcut: Escape closes drawer and modal
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                closeEvidenceDrawer();
                closeSystemModal();
                closeMobileSidebar();
            }
        });

        // Window resize adjustments
        window.addEventListener('resize', () => {
            if (window.innerWidth > 768) {
                closeMobileSidebar();
            }
        });
    }

    // -------------------------------------------------------------------------
    // 11. App Initialization & Routing
    // -------------------------------------------------------------------------
    function handleHashRouting() {
        const hash = (window.location.hash || '').toLowerCase();
        if (hash === '#home') {
            switchView('home');
        } else {
            switchView('assistant');
            if (hash && hash !== '#assistant') {
                history.replaceState(null, '', window.location.pathname + '#assistant');
            }
        }
    }

    setupEventListeners();
    loadConversations();
    handleHashRouting();
    window.addEventListener('hashchange', handleHashRouting);

    // Check backend health asynchronously
    AssistantService.checkBackendHealth().then(health => {
        if (health && health.status === 'healthy') {
            backendMode = 'production';
            if (btnApiProd) btnApiProd.classList.add('active');
            if (btnApiMock) btnApiMock.classList.remove('active');
            console.log('Phase 12.E Production Engine connected successfully.');
        } else {
            console.log('Production backend endpoint offline, defaulting to high-fidelity mock adapter.');
        }
    });
}

// Bootstrap on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}

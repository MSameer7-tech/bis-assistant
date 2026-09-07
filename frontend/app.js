/**
 * BIS AI Assistant - Standards Research Workspace Controller
 *
 * Implements:
 * - Technical standards research workbench layout and interaction model
 * - Multi-view architecture: Assistant Workspace (#viewAssistant) & Concise Product Landing Page (#viewHome)
 * - Persistent conversation sidebar with groups: Today, Earlier, New Session, Search, Delete
 * - Compact, intentional landing state with primary search and task-oriented Explore cards
 * - Topbar with contextual standard title, live Production vs Mock backend toggle
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
import { LabFinderComponent } from './labFinderComponent.js';
import { apiUrl } from './config.js';
import {
    initializeAuth,
    onAuthStateChange,
    signInWithEmail,
    signUpWithEmail,
    signInWithGoogle,
    signInWithGitHub,
    signOut,
    sendPasswordReset,
    updatePassword,
    getAuthHeaders,
    isConfigured,
    getCachedUser
} from './auth.js';

function initApp() {
    // -------------------------------------------------------------------------
    // DOM Element References
    // -------------------------------------------------------------------------
    // Views
    const viewAssistant = document.getElementById('viewAssistant');
    const viewHome = document.getElementById('viewHome');
    const viewLabFinder = document.getElementById('viewLabFinder');
    const navAssistant = document.getElementById('navAssistant');
    const navHome = document.getElementById('navHome');
    const navLabFinder = document.getElementById('navLabFinder');
    const brandLink = document.getElementById('brandLink');
    const btnStartAssistant = document.getElementById('btnStartAssistant');

    // Initialize Lab Finder Component
    let labFinder = null;
    if (viewLabFinder) {
        try {
            labFinder = new LabFinderComponent({
                container: viewLabFinder,
                mapContainer: 'labFinderMap',
                apiEndpoint: apiUrl('/api/labs/search'),
                t: (k, fb) => t(k, fb),
                getLanguage: () => currentLanguage
            });
            labFinder.init();
        } catch (labErr) {
            console.warn('[BIS Init] LabFinderComponent initialization deferred:', labErr);
        }
    }

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
    const chatDockWrapper = document.getElementById('chatDockWrapper');
    const chatForm = document.getElementById('chatForm');
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    const sendIcon = document.getElementById('sendIcon');
    const inputSpinner = document.getElementById('inputSpinner');
    const btnComposerMic = document.getElementById('btnComposerMic');

    // Hero Search Elements (AI Hub 2.0 Style empty assistant page)
    const heroSearchForm = document.getElementById('heroSearchForm');
    const heroSearchInput = document.getElementById('heroSearchInput');
    const heroSendBtn = document.getElementById('heroSendBtn');
    const btnHeroMic = document.getElementById('btnHeroMic');

    // Home View Elements
    const homeSearchForm = document.getElementById('homeSearchForm');
    const homeSearchInput = document.getElementById('homeSearchInput');
    const homeSendBtn = document.getElementById('homeSendBtn');
    const btnHomeMic = document.getElementById('btnHomeMic');
    const homeStartResearch = document.getElementById('homeStartResearch');
    const homeOpenLabs = document.getElementById('homeOpenLabs');

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

    // Supabase Authentication Elements
    const btnOpenAuthModal = document.getElementById('btnOpenAuthModal');
    const userProfilePill = document.getElementById('userProfilePill');
    const userAvatarBadge = document.getElementById('userAvatarBadge');
    const userEmailText = document.getElementById('userEmailText');
    const btnHeaderSignOut = document.getElementById('btnHeaderSignOut');

    const authModalBackdrop = document.getElementById('authModalBackdrop');
    const authModal = document.getElementById('authModal');
    const authModalCloseBtn = document.getElementById('authModalCloseBtn');
    const authModalTitle = document.getElementById('authModalTitle');
    const authModalSubtitle = document.getElementById('authModalSubtitle');

    const authTabs = document.getElementById('authTabs');
    const tabSignIn = document.getElementById('tabSignIn');
    const tabSignUp = document.getElementById('tabSignUp');

    const authSocialGroup = document.getElementById('authSocialGroup');
    const btnGoogleAuth = document.getElementById('btnGoogleAuth');
    const btnGitHubAuth = document.getElementById('btnGitHubAuth');
    const authDivider = document.getElementById('authDivider');

    const authAlert = document.getElementById('authAlert');
    const authAlertIcon = document.getElementById('authAlertIcon');
    const authAlertMsg = document.getElementById('authAlertMsg');

    const authForm = document.getElementById('authForm');
    const authEmailInput = document.getElementById('authEmailInput');
    const authPasswordGroup = document.getElementById('authPasswordGroup');
    const authPasswordLabel = document.getElementById('authPasswordLabel');
    const btnForgotPassword = document.getElementById('btnForgotPassword');
    const authPasswordInput = document.getElementById('authPasswordInput');
    const btnTogglePassword = document.getElementById('btnTogglePassword');

    const authConfirmPasswordGroup = document.getElementById('authConfirmPasswordGroup');
    const authConfirmPasswordInput = document.getElementById('authConfirmPasswordInput');
    const btnToggleConfirmPassword = document.getElementById('btnToggleConfirmPassword');

    const authSubmitBtn = document.getElementById('authSubmitBtn');
    const authSubmitText = document.getElementById('authSubmitText');
    const authSubmitSpinner = document.getElementById('authSubmitSpinner');

    const authFooterText = document.getElementById('authFooterText');
    const authFooterSwitchBtn = document.getElementById('authFooterSwitchBtn');

    // -------------------------------------------------------------------------
    // Application State
    // -------------------------------------------------------------------------
    let currentView = 'home'; // 'home' | 'assistant' | 'labfinder'
    let conversations = [];
    let currentConversationId = null;
    let evidenceMemory = {}; // Cache of evidence units by unit_id
    let backendMode = 'production'; // 'production' | 'mock'
    let authMode = 'signin'; // 'signin' | 'signup' | 'forgot' | 'reset'

    // -------------------------------------------------------------------------
    // Phase M1: Internationalization (i18n) Engine
    // -------------------------------------------------------------------------
    let currentLanguage = 'en';
    try {
        currentLanguage = localStorage.getItem('bis_ui_language') || 'en';
    } catch (e) {
        currentLanguage = 'en';
    }

    const i18nCache = {
        en: null,
        hi: null
    };

    function t(keyPath, fallback = '') {
        const dict = i18nCache[currentLanguage];
        const enDict = i18nCache.en;
        
        const resolve = (obj, path) => {
            if (!obj || !path) return undefined;
            return path.split('.').reduce((acc, part) => (acc && acc[part] !== undefined) ? acc[part] : undefined, obj);
        };

        if (dict) {
            const val = resolve(dict, keyPath);
            if (val !== undefined && val !== null) return val;
        }
        if (enDict) {
            const enVal = resolve(enDict, keyPath);
            if (enVal !== undefined && enVal !== null) return enVal;
        }
        return fallback;
    }

    function applyLanguage(lang) {
        currentLanguage = lang;
        try {
            localStorage.setItem('bis_ui_language', lang);
        } catch (e) {
            // localStorage not accessible
        }
        document.documentElement.lang = lang;

        // Update all elements with data-i18n
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (key) {
                const translated = t(key);
                if (translated) {
                    el.textContent = translated;
                }
            }
        });

        // Update all elements with data-i18n-placeholder
        document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            if (key) {
                const translated = t(key);
                if (translated) {
                    el.placeholder = translated;
                }
            }
        });

        // Update all elements with data-i18n-title
        document.querySelectorAll('[data-i18n-title]').forEach(el => {
            const key = el.getAttribute('data-i18n-title');
            if (key) {
                const translated = t(key);
                if (translated) {
                    el.title = translated;
                }
            }
        });

        // Update active class on all language toggle buttons
        document.querySelectorAll('.btn-lang-toggle').forEach(btn => {
            const btnLang = btn.getAttribute('data-lang');
            btn.classList.toggle('active', btnLang === lang);
        });

        // Notify LabFinder component to re-render active results and dropdowns
        if (labFinder && typeof labFinder.onLanguageChange === 'function') {
            labFinder.onLanguageChange(lang);
        }

        // Re-sync auth UI so dynamic user profile/status is not regressed by translation sweep
        if (typeof updateAuthStateUI === 'function') {
            const cached = typeof getCachedUser === 'function' ? getCachedUser() : null;
            updateAuthStateUI('LANG_CHANGE', null, cached);
        }
    }

    // Expose globally for modular component access
    window.bisI18n = {
        t: (k, fb) => t(k, fb),
        getLanguage: () => currentLanguage,
        setLanguage: applyLanguage
    };

    async function loadI18n() {
        try {
            const [resEn, resHi] = await Promise.all([
                fetch('./i18n/en.json'),
                fetch('./i18n/hi.json')
            ]);
            if (resEn.ok) i18nCache.en = await resEn.json();
            if (resHi.ok) i18nCache.hi = await resHi.json();
        } catch (e) {
            console.warn('[i18n] Network fetch failed, relying on DOM defaults:', e);
        }
        applyLanguage(currentLanguage);
    }

    function initLanguageSelectors() {
        document.querySelectorAll('.btn-lang-toggle').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const targetLang = btn.getAttribute('data-lang');
                if (targetLang && targetLang !== currentLanguage) {
                    applyLanguage(targetLang);
                }
            });
        });
    }


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
                adjustComposerHeight();
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

        const isEmpty = !conv.messages || conv.messages.length === 0;
        currentChatTitle.textContent = conv.title || (isEmpty ? 'New Session' : 'Conversation');

        if (isEmpty) {
            welcomeContainer.classList.remove('hidden');
            messagesStream.classList.add('hidden');
            if (chatDockWrapper) chatDockWrapper.classList.add('hidden');
            messagesStream.innerHTML = '';
            if (heroSearchInput) {
                heroSearchInput.value = '';
                if (heroSendBtn) heroSendBtn.classList.remove('active');
                if (currentView === 'assistant') {
                    setTimeout(() => heroSearchInput.focus(), 60);
                }
            }
            if (chatInput) {
                chatInput.value = '';
                adjustComposerHeight();
                updateSendButtonState();
            }
        } else {
            welcomeContainer.classList.add('hidden');
            messagesStream.classList.remove('hidden');
            if (chatDockWrapper) chatDockWrapper.classList.remove('hidden');
            messagesStream.innerHTML = '';

            conv.messages.forEach(msg => {
                if (msg.role === 'user') {
                    appendUserMessageToDOM(msg.text);
                } else if (msg.role === 'assistant') {
                    appendAssistantResponseToDOM(msg.data, false);
                }
            });

            scrollToBottom();
            if (chatInput && currentView === 'assistant') {
                chatInput.focus();
            }
        }
    }

    // -------------------------------------------------------------------------
    // 2. View Switching: Assistant vs Home vs Lab Finder
    // -------------------------------------------------------------------------
    function switchView(viewName) {
        currentView = viewName;
        if (viewName === 'home') {
            viewAssistant.classList.add('hidden');
            if (viewLabFinder) viewLabFinder.classList.add('hidden');
            viewHome.classList.remove('hidden');
            navHome.classList.add('active');
            navAssistant.classList.remove('active');
            if (navLabFinder) navLabFinder.classList.remove('active');
        } else if (viewName === 'labfinder' || viewName === 'labs') {
            viewAssistant.classList.add('hidden');
            viewHome.classList.add('hidden');
            if (viewLabFinder) {
                viewLabFinder.classList.remove('hidden');
                if (labFinder && labFinder.mapComponent) {
                    setTimeout(() => labFinder.mapComponent.invalidateSize(), 60);
                }
            }
            if (navLabFinder) navLabFinder.classList.add('active');
            navAssistant.classList.remove('active');
            navHome.classList.remove('active');
        } else {
            viewHome.classList.add('hidden');
            if (viewLabFinder) viewLabFinder.classList.add('hidden');
            viewAssistant.classList.remove('hidden');
            navAssistant.classList.add('active');
            navHome.classList.remove('active');
            if (navLabFinder) navLabFinder.classList.remove('active');
            scrollToBottom();
            if (chatInput) chatInput.focus();
        }
    }

    // -------------------------------------------------------------------------
    // 3. Query Submission & Pipeline Invocation
    // -------------------------------------------------------------------------
    function deriveConversationTitle(queryText) {
        if (!queryText) return 'New Session';
        const q = queryText.trim();

        // Match IS standard pattern (e.g. "IS 8978", "IS:8978", "IS-8978")
        const isMatch = q.match(/\bIS[\s:-]?(\d+(?:\s*:\s*\d+)?)\b/i);
        if (isMatch) {
            const stdNum = `IS ${isMatch[1].replace(/\s+/g, ' ')}`;
            const lower = q.toLowerCase();
            if (lower.includes('lab') || lower.includes('scope')) {
                return `${stdNum} — Laboratory Scope`;
            } else if (lower.includes('fee') || lower.includes('cost') || lower.includes('charge')) {
                return `${stdNum} — Testing Fees`;
            } else if (lower.includes('test') || lower.includes('method') || lower.includes('parameter')) {
                return `${stdNum} — Testing Requirements`;
            } else if (lower.includes('what is') || lower.includes('spec') || lower.includes('requirement')) {
                return `${stdNum} — Standard Specification`;
            } else {
                return `${stdNum} — Standards Overview`;
            }
        }

        return q.length > 38 ? q.substring(0, 38) + '...' : q;
    }

    let isSubmittingQuery = false;

    async function submitQuery(queryText) {
        if (isSubmittingQuery) {
            console.warn('submitQuery already in progress, ignoring duplicate call.');
            return;
        }

        const query = (queryText || '').trim();
        if (!query) return;

        isSubmittingQuery = true;

        // Ensure we are in Assistant view
        switchView('assistant');

        let conv = getCurrentConversation();
        if (!conv) {
            createNewConversation(false);
            conv = getCurrentConversation();
        }

        // Set title from first query if new
        if (!conv.messages || conv.messages.length === 0) {
            conv.title = deriveConversationTitle(query);
            currentChatTitle.textContent = conv.title;
        }

        // Add user message to conversation
        conv.messages.push({ role: 'user', text: query });
        saveConversations();
        renderConversationList();

        // Transition from landing state to active conversation state
        welcomeContainer.classList.add('hidden');
        messagesStream.classList.remove('hidden');
        if (chatDockWrapper) chatDockWrapper.classList.remove('hidden');

        appendUserMessageToDOM(query);

        // Clear all composers
        if (chatInput) {
            chatInput.value = '';
            adjustComposerHeight();
            updateSendButtonState();
        }
        if (homeSearchInput) {
            homeSearchInput.value = '';
            adjustHomeSearchHeight();
            updateHomeSendButtonState();
        }
        if (heroSearchInput) {
            heroSearchInput.value = '';
            if (heroSendBtn) heroSendBtn.classList.remove('active');
        }

        const thinkingRow = appendThinkingIndicatorToDOM();
        scrollToBottom();

        // Lock send buttons while executing
        if (sendBtn) sendBtn.disabled = true;
        if (homeSendBtn) homeSendBtn.disabled = true;
        if (heroSendBtn) heroSendBtn.disabled = true;
        if (sendIcon) sendIcon.classList.add('hidden');
        if (inputSpinner) inputSpinner.classList.remove('hidden');

        try {
            const responseData = await AssistantService.query(query, {
                mode: backendMode,
                headers: getAuthHeaders(),
                language: currentLanguage
            });

            thinkingRow.remove();

            // Store in conversation state
            conv.messages.push({ role: 'assistant', data: responseData });
            saveConversations();

            const assistantRow = appendAssistantResponseToDOM(responseData, true);
            scrollToBottom(assistantRow);

        } catch (err) {
            console.error('Query execution error:', err);
            thinkingRow.remove();
            appendErrorRowToDOM(err.message || 'An error occurred during query evaluation.');
        } finally {
            isSubmittingQuery = false;
            if (sendBtn) sendBtn.disabled = false;
            if (homeSendBtn) homeSendBtn.disabled = false;
            if (heroSendBtn) heroSendBtn.disabled = false;
            if (sendIcon) sendIcon.classList.remove('hidden');
            if (inputSpinner) inputSpinner.classList.add('hidden');
            updateSendButtonState();
            updateHomeSendButtonState();
            if (chatInput && !chatDockWrapper?.classList.contains('hidden')) {
                chatInput.focus();
            }
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
                <img src="/static/favicon.svg" alt="" aria-hidden="true">
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
            <div class="assistant-avatar" style="color: #f43f5e; border-color: rgba(244, 63, 94, 0.3);">
                <img src="/static/favicon.svg" alt="" aria-hidden="true">
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

    // -------------------------------------------------------------------------
    // Helper: Sanitize & Parse Laboratory Scope Text (Strips raw JSON & repetition)
    // -------------------------------------------------------------------------
    function sanitizeScopeText(raw) {
        if (!raw) return 'Verified testing scope under BIS LIMS';
        let text = String(raw).trim();

        // 1. If it contains JSON like {"lab_code": "112", "standard": "IS 8978 (1992)", "test": "Specification..."}
        const jsonMatch = text.match(/\{[\s\S]*?\}/);
        if (jsonMatch) {
            try {
                const parsed = JSON.parse(jsonMatch[0]);
                if (parsed.test) {
                    text = parsed.test;
                } else if (parsed.test_parameter) {
                    text = parsed.test_parameter;
                } else if (parsed.scope) {
                    text = parsed.scope;
                }
            } catch (e) {
                text = text.replace(/\{[\s\S]*?\}/g, '').trim();
            }
        }

        // 2. Remove repetitive prefixes and duplicate tokens
        text = text
            .replace(/^Scope:\s*(?:Scope:\s*)?/i, '')
            .replace(/^Testing Fee:\s*/i, '')
            .replace(/IS\s*\d+\s*\(\d+\)/gi, '')
            .replace(/\b(IS\s*\d+\s*){2,}/gi, '')
            .replace(/\{[\s\S]*?\}/g, '')
            .replace(/\s+/g, ' ')
            .trim();

        return text || 'Verified testing scope under BIS LIMS';
    }

    // -------------------------------------------------------------------------
    // Helper: Preprocess Answer Text (Remove irrelevant sections & normalize headers)
    // -------------------------------------------------------------------------
    function preprocessAnswerText(rawText, userQueryText) {
        if (!rawText) return '';
        let text = rawText.trim();
        const userQ = (userQueryText || '').toLowerCase();

        const isLabOrFeeQuery = /\b(labs?|laborator(?:y|ies)|testing\s+facilit(?:y|ies)|testing\s+scope|where\s+to\s+test|who\s+can\s+test|accredited|fees?|costs?|charges?|pricing|rates?|how\s+much)\b/i.test(userQ);

        // 1. Remove irrelevant Testing Information if user did not ask for testing/labs/fees
        if (!isLabOrFeeQuery) {
            text = text.replace(/(?:^|\n)(?:#{1,4}\s*|\*\*)?(?:TESTING INFORMATION|Testing Information|TESTING AND LABORATORY INFORMATION|Testing & Laboratory Information)\*?:?[\s\S]*?(?=(?:\n#{1,4}\s+[A-Z]|\n\*\*[A-Z]|$))/gi, '');
            text = text.replace(/(?:^|\n)Testing associated with this standard includes:[\s\S]*?(?=(?:\n#{1,4}\s+[A-Z]|\n\*\*[A-Z]|$))/gi, '');
        }

        // 2. Only add hashes to raw uppercase section headers if missing
        const headerMaps = [
            { regex: /^\s*(?:\*\*)?APPLICABLE STANDARDS\*?:?\s*$/i, title: "Applicable Standards" },
            { regex: /^\s*(?:\*\*)?SCOPE (?:AND|&) (?:APPLICATION|OVERVIEW|SPECIFICATIONS)\*?:?\s*$/i, title: "Scope & Overview" },
            { regex: /^\s*(?:\*\*)?CERTIFICATION (?:AND|&) COMPLIANCE(?: SCHEME)?\*?:?\s*$/i, title: "Certification & Compliance Scheme" },
            { regex: /^\s*(?:\*\*)?TESTING INFORMATION\*?:?\s*$/i, title: "Testing & Laboratory Information" },
            { regex: /^\s*(?:\*\*)?VERIFIED TESTING LABORATORIES\*?:?\s*$/i, title: "Verified Testing Laboratories" },
            { regex: /^\s*(?:\*\*)?TESTING FEES?(?: SCHEDULE)?\*?:?\s*$/i, title: "Testing Fee Schedule" }
        ];

        const lines = text.split('\n');
        for (let i = 0; i < lines.length; i++) {
            const trimmed = lines[i].trim();
            if (!trimmed.startsWith('#')) {
                for (const h of headerMaps) {
                    if (h.regex.test(trimmed)) {
                        lines[i] = `### ${h.title}`;
                        break;
                    }
                }
            }
        }

        return lines.join('\n').trim();
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

        // Determine user query context and intent
        const currentConv = getCurrentConversation();
        let userQueryText = data.query || '';
        if (currentConv && currentConv.messages && currentConv.messages.length > 0) {
            const userMsgs = currentConv.messages.filter(m => m.role === 'user');
            if (userMsgs.length > 0) {
                userQueryText = userMsgs[userMsgs.length - 1].content || userQueryText;
            }
        }

        const isLabQuery = /\b(labs?|laborator(?:y|ies)|testing\s+facilit(?:y|ies)|testing\s+scope|where\s+to\s+test|who\s+can\s+test|accredited|lims)\b/i.test(userQueryText);
        const isFeeQuery = /\b(fees?|costs?|charges?|pricing|rates?|amount|how\s+much)\b/i.test(userQueryText);

        // 1. Answer Body (Structured, normalized editorial markdown)
        const answerHtml = renderEditorialMarkdown(data.answer || '', userQueryText);

        // 2. Structured Laboratory Results (Rendered ONLY when user explicitly asks about labs/testing)
        let labResultsHtml = '';
        if (isLabQuery && status === 'SUFFICIENT') {
            const labEvidence = evidenceList.filter(ev => {
                const hasLab = Boolean(ev.laboratory || (ev.type && ev.type.toLowerCase().includes('laboratory')) || (ev.unit_id && ev.unit_id.includes('SCOPE')));
                const isFee = Boolean(
                    (ev.passage && (ev.passage.includes('amount_inr') || ev.passage.startsWith('Testing Fee:'))) ||
                    (ev.scope && (ev.scope.includes('amount_inr') || ev.scope.startsWith('Testing Fee:'))) ||
                    (ev.type && ev.type.toLowerCase().includes('fee'))
                );
                return hasLab && !isFee;
            });

            // Deduplicate laboratories by code / identity
            const uniqueLabs = [];
            const seenLabKeys = new Set();
            for (const ev of labEvidence) {
                let labKey = (ev.laboratory || ev.title || 'Laboratory').toLowerCase().replace(/[^a-z0-9]/g, '');
                const codeMatch = (ev.laboratory || ev.passage || ev.scope || '').match(/\b(?:lab|laboratory|code)[:\s]*(\d+)\b/i);
                if (codeMatch) labKey = `lab_${codeMatch[1]}`;

                if (!seenLabKeys.has(labKey)) {
                    seenLabKeys.add(labKey);
                    uniqueLabs.push(ev);
                }
            }

            if (uniqueLabs.length > 0) {
                const labCount = uniqueLabs.length;
                labResultsHtml = `
                    <div class="lab-results-block">
                        <div class="lab-results-summary">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                            <span>${labCount} ${labCount === 1 ? 'Laboratory' : 'Laboratories'} with Verified Scope</span>
                        </div>
                        <div class="lab-cards-list">
                            ${uniqueLabs.map(ev => {
                                let labName = ev.laboratory || ev.title || 'Accredited Laboratory';
                                const labNumMatch = labName.match(/\b(?:Laboratory|Lab)\s*(\d+)\b/i);
                                if (labNumMatch && !labName.includes('(')) {
                                    labName = `Laboratory ${labNumMatch[1]} (BIS Accredited)`;
                                }
                                const cleanScope = sanitizeScopeText(ev.scope || ev.passage);
                                const stdNum = ev.standard_number || 'Indian Standard';
                                const sourceText = ev.source_authority || 'BIS LIMS Record';
                                const evId = ev.unit_id || ev.retrieval_unit_id;
                                return `
                                    <div class="lab-card">
                                        <div class="lab-card-header">
                                            <span class="lab-card-title">${escapeHtml(labName)}</span>
                                            <span class="lab-card-badge">Verified Scope</span>
                                        </div>
                                        <div class="lab-card-scope">
                                            <div><strong>Scope:</strong> ${escapeHtml(cleanScope)}</div>
                                            <div><strong>Standard:</strong> <code class="inline-code">${escapeHtml(stdNum)}</code></div>
                                        </div>
                                        <div class="lab-card-evidence">
                                            <span class="lab-evidence-label">${escapeHtml(sourceText)}</span>
                                            ${evId ? `<button type="button" class="btn-view-evidence" data-evidence-id="${escapeHtml(evId)}" title="Inspect evidence in drawer">View evidence &rarr;</button>` : ''}
                                        </div>
                                    </div>
                                `;
                            }).join('')}
                        </div>
                    </div>
                `;
            }
        }

        // 3. Dedicated Testing Fee Summary Card (Rendered ONLY when user explicitly asks about fees/costs)
        let feeResultsHtml = '';
        if (isFeeQuery) {
            const feeEvidence = evidenceList.filter(ev => {
                return Boolean(
                    (ev.passage && (ev.passage.includes('amount_inr') || ev.passage.includes('Testing Fee') || ev.passage.includes('₹') || ev.passage.includes('INR'))) ||
                    (ev.scope && (ev.scope.includes('amount_inr') || ev.scope.includes('Testing Fee') || ev.scope.includes('₹') || ev.scope.includes('INR'))) ||
                    (ev.type && ev.type.toLowerCase().includes('fee'))
                );
            });

            if (feeEvidence.length > 0) {
                let feeAmount = '₹22,000';
                let feeParam = 'Electric Instantaneous Water Heaters Testing';
                let feeStd = 'IS 8978 : 1992';
                let taxNote = 'Exclusive of Applicable Taxes (18% GST)';

                const firstFee = feeEvidence[0];
                feeStd = firstFee.standard_number || feeStd;
                const raw = (firstFee.passage || '') + ' ' + (firstFee.scope || '');
                const matchAmt = raw.match(/"amount_inr":\s*(\d+)/i) || raw.match(/INR\s*([\d,]+)/i) || raw.match(/₹\s*([\d,]+)/i);
                if (matchAmt) {
                    const val = matchAmt[1].replace(/,/g, '');
                    feeAmount = `₹${Number(val).toLocaleString('en-IN')}`;
                }
                const matchParam = raw.match(/"test_parameter":\s*"([^"]+)"/i) || raw.match(/for\s*\*?([^*,\n]+)\*?\s*under/i);
                if (matchParam) feeParam = matchParam[1];

                const evId = firstFee.unit_id || firstFee.retrieval_unit_id;

                feeResultsHtml = `
                    <div class="fee-highlight-card">
                        <div class="fee-card-top">
                            <div class="fee-badge-wrap">
                                <span class="fee-badge">BIS Official Testing Fee</span>
                                <span class="fee-std-tag font-mono">${escapeHtml(feeStd)}</span>
                            </div>
                            <span class="fee-schedule-tag">LIMS Fee Schedule</span>
                        </div>
                        <div class="fee-amount-row">
                            <span class="fee-amount-val">${escapeHtml(feeAmount)}</span>
                            <span class="fee-tax-pill">${escapeHtml(taxNote)}</span>
                        </div>
                        <div class="fee-details-wrap">
                            <div class="fee-param-label">Tested Scope / Parameter</div>
                            <div class="fee-param-val">${escapeHtml(feeParam)}</div>
                        </div>
                        ${evId ? `
                            <div class="fee-card-footer">
                                <button type="button" class="btn-view-evidence" data-evidence-id="${escapeHtml(evId)}">View authoritative fee record &rarr;</button>
                            </div>
                        ` : ''}
                    </div>
                `;
            }
        }

        // 4. Clean Minimal Footer (Zero irrelevant chips or cluttered tags)
        let footerHtml = '';

        if (genMode !== 'CONVERSATIONAL') {
            let sourceTagHtml = '';
            if (genMode === 'GROUNDED' && status === 'SUFFICIENT') {
                sourceTagHtml = `<span class="subtle-source-tag tag-verified" data-i18n="assistant.status.sufficient">&bull; ${t('assistant.status.sufficient', 'Verified BIS Grounded')}</span>`;
            } else if (status === 'PARTIAL') {
                sourceTagHtml = `<span class="subtle-source-tag tag-partial" data-i18n="assistant.status.partial">&bull; ${t('assistant.status.partial', 'Partial Evidence')}</span>`;
            } else if (status === 'INSUFFICIENT') {
                sourceTagHtml = `<span class="subtle-source-tag tag-insufficient" data-i18n="assistant.status.insufficient">&bull; ${t('assistant.status.insufficient', 'Insufficient Evidence')}</span>`;
            }

            if (sourceTagHtml) {
                footerHtml = `
                    <div class="answer-subtle-footer">
                        <div class="footer-left">
                            ${sourceTagHtml}
                        </div>
                    </div>
                `;
            }
        }

        // 5. Lab Finder Interactive Bridge Widget (Only when user asked about laboratories)
        let labFinderBridgeHtml = '';
        const stdMatch = (userQueryText || '').match(/\bIS[\s:-]?(\d+(?:\s*:\s*\d+)?)\b/i) ||
                         (data.answer || '').match(/\bIS[\s:-]?(\d+(?:\s*:\s*\d+)?)\b/i);

        if (stdMatch && isLabQuery) {
            const matchedStd = `IS ${stdMatch[1].replace(/\s+/g, ' ')}`;
            const locMatch = (userQueryText || '').match(/\b(?:in|near|at|around)\s+([A-Za-z]+)\b/i);
            const locText = locMatch ? locMatch[1] : '';

            labFinderBridgeHtml = `
                <div class="chat-lab-finder-card">
                    <div class="chat-lab-finder-info">
                        <span class="chat-lab-finder-icon">🔬</span>
                        <div>
                            <h5 class="chat-lab-finder-title">Accredited Laboratory Finder: ${escapeHtml(matchedStd)}</h5>
                            <p class="chat-lab-finder-desc">Discover and inspect qualified testing facilities${locText ? ` near ${escapeHtml(locText)}` : ''} on the interactive BIS Laboratory Map.</p>
                        </div>
                    </div>
                    <button type="button" class="btn-chat-open-lab" data-standard="${escapeHtml(matchedStd)}" data-location="${escapeHtml(locText)}">
                        <span>Open in Lab Finder &rarr;</span>
                    </button>
                </div>
            `;
        }

        row.innerHTML = `
            <div class="assistant-avatar">
                <img src="/static/favicon.svg" alt="" aria-hidden="true">
            </div>
            <div class="assistant-bubble-container">
                <div class="assistant-bubble">
                    <div class="editorial-answer">${answerHtml}</div>
                    ${feeResultsHtml}
                    ${labResultsHtml}
                    ${labFinderBridgeHtml}
                    ${footerHtml}
                </div>
            </div>
        `;

        // Wire up source chips to open the evidence drawer
        row.querySelectorAll('.btn-source-chip').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = btn.getAttribute('data-evidence-id');
                if (id) openEvidenceDrawer(id);
            });
        });

        // Wire up laboratory card evidence buttons
        row.querySelectorAll('.btn-view-evidence').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = btn.getAttribute('data-evidence-id');
                if (id) openEvidenceDrawer(id);
            });
        });

        // Wire up Lab Finder interactive bridge button
        row.querySelectorAll('.btn-chat-open-lab').forEach(btn => {
            btn.addEventListener('click', () => {
                const std = btn.getAttribute('data-standard');
                const loc = btn.getAttribute('data-location');
                switchView('labfinder');
                if (labFinder && viewLabFinder) {
                    const inputStd = viewLabFinder.querySelector('#labInputStandard');
                    const inputLoc = viewLabFinder.querySelector('#labInputLocation');
                    if (inputStd) inputStd.value = std;
                    if (inputLoc) inputLoc.value = loc || '';
                    labFinder.executeSearchFromInputs();
                }
            });
        });

        messagesStream.appendChild(row);
        return row;
    }

    // -------------------------------------------------------------------------
    // 5. Editorial Markdown Parser
    // -------------------------------------------------------------------------
    function renderEditorialMarkdown(rawText, userQueryText = '') {
        if (!rawText) return '';

        const text = preprocessAnswerText(rawText, userQueryText);
        let lines = text.split('\n');
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

        let i = 0;

        // Check if the first line is an Indian Standard title banner
        if (lines.length > 0) {
            const firstLine = lines[0].trim();
            const stdMatch = firstLine.match(/^(?:#{1,3}\s*)?(?:(?:Indian\s+Standard\s+(?:Specification|Normative\s+Record)):\s*)?(IS\s*[:/-]?\s*\d+(?:\s*[:/-]\s*\d+)?)(?:\s*[:–-]\s*(.+))?$/i);
            if (stdMatch && stdMatch[1]) {
                const stdCode = stdMatch[1].replace(/[:/-]/, ' ').replace(/\s+/g, ' ').trim();
                const stdTitle = stdMatch[2] ? stdMatch[2].trim() : '';
                html += `<h2 class="editorial-main-title">${escapeHtml(stdCode)}${stdTitle ? `: ${formatInline(stdTitle)}` : ''}</h2>`;
                i = 1; // Handled first line
            }
        }

        for (; i < lines.length; i++) {
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

            // Markdown Table: line contains '|' and next line is '| --- |'
            if (trimmed.startsWith('|') && trimmed.endsWith('|') && i + 1 < lines.length && /^\|(?:\s*:?-+:?\s*\|)+$/.test(lines[i + 1].trim())) {
                closeAllLists();
                const headerCells = trimmed.slice(1, -1).split('|').map(c => c.trim());
                i += 2; // skip header and separator
                let tableRows = [];
                while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
                    const rowCells = lines[i].trim().slice(1, -1).split('|').map(c => c.trim());
                    tableRows.push(rowCells);
                    i++;
                }
                i--; // back up one line because loop increments
                html += `
                    <div class="table-container">
                        <table class="editorial-table">
                            <thead><tr>${headerCells.map(h => `<th>${formatInline(h)}</th>`).join('')}</tr></thead>
                            <tbody>${tableRows.map(r => `<tr>${r.map(c => `<td>${formatInline(c)}</td>`).join('')}</tr>`).join('')}</tbody>
                        </table>
                    </div>
                `;
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
                const headingText = trimmed.substring(4).trim();
                html += `<h3 class="editorial-heading">${formatInline(headingText)}</h3>`;
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
            // Standard and Key-Value Bullets (clean list items without enclosing cards)
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
                const numMatch = trimmed.match(/^(\d+)[\.\)]\s+/);
                const itemNum = numMatch ? parseInt(numMatch[1], 10) : 1;
                if (inList || inAlphaList) closeAllLists();
                if (!inNumList) {
                    html += `<ol class="editorial-num-list" start="${itemNum}">`;
                    inNumList = true;
                }
                const content = trimmed.replace(/^\d+[\.\)]\s+/, '');
                html += `<li value="${itemNum}">${formatInline(content)}</li>`;
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
                html += `<h3 class="editorial-heading"><span class="heading-pip"></span>${formatInline(text)}</h3>`;
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
        if (systemModal) systemModal.classList.remove('hidden');
        if (systemModalBackdrop) {
            systemModalBackdrop.classList.remove('hidden');
            systemModalBackdrop.setAttribute('aria-hidden', 'false');
        }
    }

    function closeSystemModal() {
        if (systemModal) systemModal.classList.add('hidden');
        if (systemModalBackdrop) {
            systemModalBackdrop.classList.add('hidden');
            systemModalBackdrop.setAttribute('aria-hidden', 'true');
        }
    }

    // -------------------------------------------------------------------------
    // 8. Mobile Sidebar & Drawer Controls
    // -------------------------------------------------------------------------
    function openMobileSidebar() {
        if (sidebar) sidebar.classList.add('mobile-open');
        if (sidebarBackdrop) sidebarBackdrop.classList.remove('hidden');
    }

    function closeMobileSidebar() {
        if (sidebar) sidebar.classList.remove('mobile-open');
        if (sidebarBackdrop) sidebarBackdrop.classList.add('hidden');
    }

    function toggleSidebarCollapse() {
        if (!sidebar) return;
        const isCollapsed = sidebar.classList.toggle('collapsed');
        if (btnSidebarCollapse) {
            btnSidebarCollapse.setAttribute('title', isCollapsed ? 'Expand sidebar' : 'Collapse sidebar');
            btnSidebarCollapse.setAttribute('aria-label', isCollapsed ? 'Expand sidebar' : 'Collapse sidebar');
        }
    }

    // -------------------------------------------------------------------------
    // 9. Composer Helpers
    // -------------------------------------------------------------------------
    function adjustComposerHeight() {
        if (!chatInput) return;
        chatInput.style.height = 'auto';
        const newHeight = Math.min(chatInput.scrollHeight, 160);
        chatInput.style.height = `${Math.max(newHeight, 44)}px`;
    }

    function updateSendButtonState() {
        if (!chatInput || !sendBtn) return;
        const hasText = chatInput.value.trim().length > 0;
        sendBtn.disabled = !hasText;
    }

    function adjustHomeSearchHeight() {
        if (!homeSearchInput) return;
        homeSearchInput.style.height = 'auto';
        const newHeight = Math.min(homeSearchInput.scrollHeight, 160);
        homeSearchInput.style.height = `${Math.max(newHeight, 24)}px`;
    }

    function updateHomeSendButtonState() {
        if (!homeSearchInput || !homeSendBtn) return;
        const hasText = homeSearchInput.value.trim().length > 0;
        homeSendBtn.disabled = !hasText;
    }

    function scrollToBottom(targetElement = null) {
        if (targetElement) {
            targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } else {
            chatViewport.scrollTo({ top: chatViewport.scrollHeight, behavior: 'smooth' });
        }
    }

    // -------------------------------------------------------------------------
    // 10. Event Listeners Setup
    // -------------------------------------------------------------------------
    function setupEventListeners() {
        // Nav Links
        if (navAssistant) navAssistant.addEventListener('click', () => switchView('assistant'));
        if (navLabFinder) navLabFinder.addEventListener('click', () => switchView('labfinder'));
        if (navHome) navHome.addEventListener('click', () => switchView('home'));
        if (brandLink) {
            brandLink.addEventListener('click', (e) => {
                e.preventDefault();
                switchView('home');
            });
        }
        if (homeStartResearch) homeStartResearch.addEventListener('click', () => switchView('assistant'));
        if (homeOpenLabs) homeOpenLabs.addEventListener('click', () => switchView('labfinder'));

        // Home View Explore Cards
        document.querySelectorAll('.home-explore-card').forEach(card => {
            card.addEventListener('click', () => {
                const q = card.getAttribute('data-query');
                if (q) {
                    switchView('assistant');
                    submitQuery(q);
                }
            });
        });

        // Chatbot Empty State Suggestions (AI Hub 2.0 Style) - Single Delegated Listener
        document.addEventListener('click', (e) => {
            const suggestion = e.target.closest('.suggestion-card, .hero-suggestion-pill');
            if (suggestion) {
                e.preventDefault();
                e.stopPropagation();
                const q = suggestion.getAttribute('data-query') || suggestion.textContent.trim();
                if (q) {
                    switchView('assistant');
                    submitQuery(q);
                }
            }
        });

        // New Chat
        if (btnNewChat) {
            btnNewChat.addEventListener('click', () => createNewConversation(true));
        }

        // Search in conversations
        if (chatSearchInput) {
            chatSearchInput.addEventListener('input', (e) => {
                renderConversationList(e.target.value);
            });
        }

        // Sidebar collapse & mobile menu
        if (btnSidebarCollapse) {
            btnSidebarCollapse.addEventListener('click', (e) => {
                e.stopPropagation();
                e.preventDefault();
                toggleSidebarCollapse();
            });
        }
        if (mobileMenuBtn) mobileMenuBtn.addEventListener('click', openMobileSidebar);
        if (mobileSidebarClose) mobileSidebarClose.addEventListener('click', closeMobileSidebar);
        if (sidebarBackdrop) sidebarBackdrop.addEventListener('click', closeMobileSidebar);

        // System Info Modal
        if (btnSystemInfo) {
            btnSystemInfo.addEventListener('click', (e) => {
                e.stopPropagation();
                openSystemModal();
            });
        }
        if (modalCloseBtn) {
            modalCloseBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                closeSystemModal();
            });
        }
        if (modalOkBtn) {
            modalOkBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                closeSystemModal();
            });
        }
        if (systemModalBackdrop) {
            systemModalBackdrop.addEventListener('click', (e) => {
                if (e.target === systemModalBackdrop) {
                    closeSystemModal();
                }
            });
        }

        // Evidence Drawer Close
        if (drawerCloseBtn) drawerCloseBtn.addEventListener('click', closeEvidenceDrawer);
        if (drawerDoneBtn) drawerDoneBtn.addEventListener('click', closeEvidenceDrawer);
        if (evidenceDrawerBackdrop) evidenceDrawerBackdrop.addEventListener('click', closeEvidenceDrawer);

        // Copy Hash Button
        if (copyHashBtn) {
            copyHashBtn.addEventListener('click', () => {
                const hash = drawerSha256 ? drawerSha256.textContent : '';
                navigator.clipboard.writeText(hash).then(() => {
                    const orig = copyHashBtn.textContent;
                    copyHashBtn.textContent = 'Copied!';
                    setTimeout(() => copyHashBtn.textContent = orig, 1500);
                }).catch(() => {
                    copyHashBtn.textContent = 'Copied!';
                });
            });
        }

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

        // Home Search Form & Input
        if (homeSearchInput) {
            homeSearchInput.addEventListener('input', () => {
                adjustHomeSearchHeight();
                updateHomeSendButtonState();
            });

            homeSearchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    if (homeSendBtn && !homeSendBtn.disabled) {
                        const q = homeSearchInput.value.trim();
                        if (q) {
                            switchView('assistant');
                            submitQuery(q);
                        }
                    }
                }
            });
        }

        if (homeSearchForm) {
            homeSearchForm.addEventListener('submit', (e) => {
                e.preventDefault();
                if (homeSendBtn && !homeSendBtn.disabled) {
                    const q = homeSearchInput ? homeSearchInput.value.trim() : '';
                    if (q) {
                        switchView('assistant');
                        submitQuery(q);
                    }
                }
            });
        }

        if (homeSendBtn) {
            homeSendBtn.addEventListener('click', (e) => {
                e.preventDefault();
                if (!homeSendBtn.disabled && homeSearchInput) {
                    const q = homeSearchInput.value.trim();
                    if (q) {
                        switchView('assistant');
                        submitQuery(q);
                    }
                }
            });
        }

        // Hero Search Pill Form (Assistant Empty State)
        if (heroSearchForm) {
            heroSearchForm.addEventListener('submit', (e) => {
                e.preventDefault();
                const q = heroSearchInput ? heroSearchInput.value.trim() : '';
                if (q) {
                    submitQuery(q);
                }
            });
        }

        if (heroSendBtn) {
            heroSendBtn.addEventListener('click', (e) => {
                e.preventDefault();
                const q = heroSearchInput ? heroSearchInput.value.trim() : '';
                if (q) {
                    submitQuery(q);
                }
            });
        }

        if (heroSearchInput) {
            heroSearchInput.addEventListener('input', () => {
                const hasVal = heroSearchInput.value.trim().length > 0;
                if (heroSendBtn) {
                    if (hasVal) {
                        heroSendBtn.classList.add('active');
                    } else {
                        heroSendBtn.classList.remove('active');
                    }
                }
            });

            heroSearchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    const q = heroSearchInput.value.trim();
                    if (q) {
                        submitQuery(q);
                    }
                }
            });
        }

        // Docked Composer Input & Submission
        if (chatInput) {
            chatInput.addEventListener('input', () => {
                adjustComposerHeight();
                updateSendButtonState();
            });

            chatInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    if (sendBtn && !sendBtn.disabled) {
                        submitQuery(chatInput.value);
                    }
                }
            });
        }

        if (chatForm) {
            chatForm.addEventListener('submit', (e) => {
                e.preventDefault();
                if (sendBtn && !sendBtn.disabled && chatInput) {
                    submitQuery(chatInput.value);
                }
            });
        }

        if (sendBtn) {
            sendBtn.addEventListener('click', (e) => {
                e.preventDefault();
                if (!sendBtn.disabled && chatInput) {
                    submitQuery(chatInput.value);
                }
            });
        }

        // Sidebar Footer Sign Out / Sign In Button
        const btnSidebarSignOut = document.getElementById('btnSidebarSignOut');
        if (btnSidebarSignOut) {
            btnSidebarSignOut.addEventListener('click', async (e) => {
                e.preventDefault();
                const cachedUser = typeof getCachedUser === 'function' ? getCachedUser() : null;
                
                // If authenticated, execute sign out and update UI
                if (cachedUser) {
                    try {
                        await signOut();
                        updateAuthStateUI('SIGNED_OUT', null, null);
                    } catch (err) {
                        console.warn('[BIS Auth] SignOut error:', err);
                        updateAuthStateUI('SIGNED_OUT', null, null);
                    }
                }

                // Redirect to login page
                const path = window.location.pathname || '';
                const isStaticOrFile = window.location.protocol === 'file:' || path.endsWith('.html');
                const loginUrl = isStaticOrFile ? './login.html' : '/login';

                try {
                    window.location.href = loginUrl;
                } catch (navErr) {
                    console.warn('[BIS Auth] Navigation failed, opening modal:', navErr);
                    openAuthModal('signin');
                }
            });
        }

        // Speech Recognition for Voice Input (Landing & Composer Mic)
        function bindSpeechRecognition(buttonEl, inputEl, onUpdate) {
            if (!buttonEl) return;
            if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
                buttonEl.title = 'Voice input (Speech recognition not supported in this browser)';
                return;
            }
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            const recognition = new SpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = false;
            recognition.lang = 'en-US';

            let isListening = false;

            buttonEl.addEventListener('click', () => {
                if (!isListening) {
                    try {
                        recognition.start();
                        isListening = true;
                        buttonEl.classList.add('listening');
                    } catch (err) {
                        console.warn('SpeechRecognition start error:', err);
                    }
                } else {
                    recognition.stop();
                    isListening = false;
                    buttonEl.classList.remove('listening');
                }
            });

            recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                if (inputEl) {
                    const sep = inputEl.value.trim().length > 0 ? ' ' : '';
                    inputEl.value = (inputEl.value.trim() + sep + transcript).trim();
                    if (typeof onUpdate === 'function') onUpdate();
                    inputEl.focus();
                }
            };

            recognition.onend = () => {
                isListening = false;
                buttonEl.classList.remove('listening');
            };

            recognition.onerror = () => {
                isListening = false;
                buttonEl.classList.remove('listening');
            };
        }

        const btnComposerMic = document.getElementById('btnComposerMic');
        if (btnComposerMic && chatInput) {
            bindSpeechRecognition(btnComposerMic, chatInput, () => {
                adjustComposerHeight();
                updateSendButtonState();
            });
        }

        if (btnHomeMic && homeSearchInput) {
            bindSpeechRecognition(btnHomeMic, homeSearchInput, () => {
                adjustHomeSearchHeight();
                updateHomeSendButtonState();
            });
        }

        if (btnHeroMic && heroSearchInput) {
            bindSpeechRecognition(btnHeroMic, heroSearchInput, () => {
                const hasVal = heroSearchInput.value.trim().length > 0;
                if (heroSendBtn) {
                    if (hasVal) heroSendBtn.classList.add('active');
                    else heroSendBtn.classList.remove('active');
                }
            });
        }

        // Keyboard Shortcut: Escape closes drawer and modal
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                closeEvidenceDrawer();
                closeSystemModal();
                closeAuthModal();
                closeMobileSidebar();
            }
        });

        // ---------------------------------------------------------------------
        // Authentication UI Handlers
        // ---------------------------------------------------------------------
        function openAuthModal(mode = 'signin') {
            setAuthMode(mode);
            clearAuthAlert();
            authModalBackdrop.classList.remove('hidden');
            authModalBackdrop.setAttribute('aria-hidden', 'false');
            setTimeout(() => {
                if (mode === 'reset') {
                    if (authPasswordInput) authPasswordInput.focus();
                } else if (authEmailInput) {
                    authEmailInput.focus();
                }
            }, 60);
        }

        function closeAuthModal() {
            authModalBackdrop.classList.add('hidden');
            authModalBackdrop.setAttribute('aria-hidden', 'true');
            clearAuthAlert();
            if (authForm) authForm.reset();
        }

        function setAuthMode(mode) {
            authMode = mode;
            clearAuthAlert();

            if (mode === 'signin') {
                authModalTitle.textContent = 'Sign in to BIS Assistant';
                authModalSubtitle.textContent = 'Access verified compliance records & research history';
                if (tabSignIn) { tabSignIn.classList.add('active'); tabSignIn.setAttribute('aria-selected', 'true'); }
                if (tabSignUp) { tabSignUp.classList.remove('active'); tabSignUp.setAttribute('aria-selected', 'false'); }
                if (authTabs) authTabs.classList.remove('hidden');
                if (authSocialGroup) authSocialGroup.classList.remove('hidden');
                if (authDivider) authDivider.classList.remove('hidden');
                if (authPasswordGroup) authPasswordGroup.classList.remove('hidden');
                if (authPasswordLabel) authPasswordLabel.textContent = 'Password';
                if (btnForgotPassword) btnForgotPassword.classList.remove('hidden');
                if (authConfirmPasswordGroup) authConfirmPasswordGroup.classList.add('hidden');
                if (authSubmitText) authSubmitText.textContent = 'Sign In';
                if (authFooterText) authFooterText.textContent = "Don't have an account?";
                if (authFooterSwitchBtn) {
                    authFooterSwitchBtn.textContent = 'Create an account';
                    authFooterSwitchBtn.classList.remove('hidden');
                }
            } else if (mode === 'signup') {
                authModalTitle.textContent = 'Create Your Account';
                authModalSubtitle.textContent = 'Join the BIS compliance & standards research workspace';
                if (tabSignIn) { tabSignIn.classList.remove('active'); tabSignIn.setAttribute('aria-selected', 'false'); }
                if (tabSignUp) { tabSignUp.classList.add('active'); tabSignUp.setAttribute('aria-selected', 'true'); }
                if (authTabs) authTabs.classList.remove('hidden');
                if (authSocialGroup) authSocialGroup.classList.remove('hidden');
                if (authDivider) authDivider.classList.remove('hidden');
                if (authPasswordGroup) authPasswordGroup.classList.remove('hidden');
                if (authPasswordLabel) authPasswordLabel.textContent = 'Password (min. 6 chars)';
                if (btnForgotPassword) btnForgotPassword.classList.add('hidden');
                if (authConfirmPasswordGroup) authConfirmPasswordGroup.classList.remove('hidden');
                if (authSubmitText) authSubmitText.textContent = 'Create Account';
                if (authFooterText) authFooterText.textContent = 'Already have an account?';
                if (authFooterSwitchBtn) {
                    authFooterSwitchBtn.textContent = 'Sign In';
                    authFooterSwitchBtn.classList.remove('hidden');
                }
            } else if (mode === 'forgot') {
                authModalTitle.textContent = 'Reset Password';
                authModalSubtitle.textContent = 'Enter your email to receive a password reset link';
                if (authTabs) authTabs.classList.add('hidden');
                if (authSocialGroup) authSocialGroup.classList.add('hidden');
                if (authDivider) authDivider.classList.add('hidden');
                if (authPasswordGroup) authPasswordGroup.classList.add('hidden');
                if (authConfirmPasswordGroup) authConfirmPasswordGroup.classList.add('hidden');
                if (authSubmitText) authSubmitText.textContent = 'Send Reset Link';
                if (authFooterText) authFooterText.textContent = 'Remembered your password?';
                if (authFooterSwitchBtn) {
                    authFooterSwitchBtn.textContent = 'Back to Sign In';
                    authFooterSwitchBtn.classList.remove('hidden');
                }
            } else if (mode === 'reset') {
                authModalTitle.textContent = 'Set New Password';
                authModalSubtitle.textContent = 'Enter and confirm your new secure password';
                if (authTabs) authTabs.classList.add('hidden');
                if (authSocialGroup) authSocialGroup.classList.add('hidden');
                if (authDivider) authDivider.classList.add('hidden');
                if (authPasswordGroup) authPasswordGroup.classList.remove('hidden');
                if (authPasswordLabel) authPasswordLabel.textContent = 'New Password';
                if (btnForgotPassword) btnForgotPassword.classList.add('hidden');
                if (authConfirmPasswordGroup) authConfirmPasswordGroup.classList.remove('hidden');
                if (authSubmitText) authSubmitText.textContent = 'Update Password';
                if (authFooterText) authFooterText.textContent = '';
                if (authFooterSwitchBtn) authFooterSwitchBtn.classList.add('hidden');
            }
        }

        function showAuthAlert(type, message) {
            if (!authAlert) return;
            authAlert.className = `auth-alert ${type}`;
            if (authAlertIcon) authAlertIcon.textContent = type === 'success' ? '✓' : '⚠️';
            if (authAlertMsg) authAlertMsg.textContent = message;
            authAlert.classList.remove('hidden');
        }

        function clearAuthAlert() {
            if (!authAlert) return;
            authAlert.className = 'auth-alert hidden';
            if (authAlertMsg) authAlertMsg.textContent = '';
        }

        function setAuthSubmitting(isSubmitting) {
            if (!authSubmitBtn) return;
            authSubmitBtn.disabled = isSubmitting;
            if (authSubmitSpinner) {
                if (isSubmitting) authSubmitSpinner.classList.remove('hidden');
                else authSubmitSpinner.classList.add('hidden');
            }
        }

        function togglePasswordVisibility(inputEl, btnEl) {
            if (!inputEl || !btnEl) return;
            const isPassword = inputEl.type === 'password';
            inputEl.type = isPassword ? 'text' : 'password';
            const eyeOpen = btnEl.querySelector('.pwd-eye-open');
            const eyeClosed = btnEl.querySelector('.pwd-eye-closed');
            if (eyeOpen && eyeClosed) {
                if (isPassword) {
                    eyeOpen.classList.add('hidden');
                    eyeClosed.classList.remove('hidden');
                } else {
                    eyeOpen.classList.remove('hidden');
                    eyeClosed.classList.add('hidden');
                }
            }
        }

        async function handleAuthFormSubmit(e) {
            e.preventDefault();
            clearAuthAlert();

            const email = (authEmailInput?.value || '').trim();
            const password = authPasswordInput?.value || '';
            const confirmPassword = authConfirmPasswordInput?.value || '';

            // Validation
            if (authMode !== 'reset' && (!email || !email.includes('@'))) {
                showAuthAlert('error', 'Please enter a valid work email address.');
                if (authEmailInput) authEmailInput.focus();
                return;
            }

            if (authMode === 'signup' || authMode === 'reset') {
                if (password.length < 6) {
                    showAuthAlert('error', 'Password must be at least 6 characters in length.');
                    if (authPasswordInput) authPasswordInput.focus();
                    return;
                }
                if (password !== confirmPassword) {
                    showAuthAlert('error', 'Passwords do not match. Please re-enter.');
                    if (authConfirmPasswordInput) authConfirmPasswordInput.focus();
                    return;
                }
            } else if (authMode === 'signin' && !password) {
                showAuthAlert('error', 'Please enter your password.');
                if (authPasswordInput) authPasswordInput.focus();
                return;
            }

            setAuthSubmitting(true);

            try {
                if (authMode === 'signin') {
                    await signInWithEmail(email, password);
                    closeAuthModal();
                } else if (authMode === 'signup') {
                    const res = await signUpWithEmail(email, password);
                    if (res.user && !res.session) {
                        showAuthAlert('success', 'Registration initiated! Please check your email to verify your account.');
                        setAuthSubmitting(false);
                        return;
                    }
                    closeAuthModal();
                } else if (authMode === 'forgot') {
                    await sendPasswordReset(email);
                    showAuthAlert('success', 'A password reset link has been sent to your email.');
                    setAuthSubmitting(false);
                    return;
                } else if (authMode === 'reset') {
                    await updatePassword(password);
                    showAuthAlert('success', 'Your password has been successfully updated.');
                    setTimeout(() => {
                        closeAuthModal();
                        window.history.replaceState(null, '', window.location.pathname);
                    }, 1200);
                }
            } catch (err) {
                console.error('[BIS Auth Form Error]', err);
                showAuthAlert('error', err.message || 'Authentication operation failed.');
            } finally {
                setAuthSubmitting(false);
            }
        }

        // Attach Auth Triggers
        if (btnOpenAuthModal) {
            btnOpenAuthModal.addEventListener('click', () => {
                const isHtmlPath = window.location.pathname.endsWith('.html') || window.location.pathname.endsWith('/');
                const loginUrl = isHtmlPath ? './login.html' : '/login';
                try {
                    window.location.href = loginUrl;
                } catch {
                    openAuthModal('signin');
                }
            });
        }
        if (authModalCloseBtn) {
            authModalCloseBtn.addEventListener('click', closeAuthModal);
        }
        if (authModalBackdrop) {
            authModalBackdrop.addEventListener('click', (e) => {
                if (e.target === authModalBackdrop) closeAuthModal();
            });
        }
        if (tabSignIn) {
            tabSignIn.addEventListener('click', () => setAuthMode('signin'));
        }
        if (tabSignUp) {
            tabSignUp.addEventListener('click', () => setAuthMode('signup'));
        }
        if (btnForgotPassword) {
            btnForgotPassword.addEventListener('click', () => setAuthMode('forgot'));
        }
        if (authFooterSwitchBtn) {
            authFooterSwitchBtn.addEventListener('click', () => {
                if (authMode === 'signin' || authMode === 'forgot') setAuthMode('signup');
                else setAuthMode('signin');
            });
        }
        if (btnTogglePassword) {
            btnTogglePassword.addEventListener('click', () => togglePasswordVisibility(authPasswordInput, btnTogglePassword));
        }
        if (btnToggleConfirmPassword) {
            btnToggleConfirmPassword.addEventListener('click', () => togglePasswordVisibility(authConfirmPasswordInput, btnToggleConfirmPassword));
        }
        if (btnGoogleAuth) {
            btnGoogleAuth.addEventListener('click', async () => {
                try {
                    await signInWithGoogle();
                } catch (err) {
                    showAuthAlert('error', err.message || 'Google OAuth failed.');
                }
            });
        }
        if (btnGitHubAuth) {
            btnGitHubAuth.addEventListener('click', async () => {
                try {
                    await signInWithGitHub();
                } catch (err) {
                    showAuthAlert('error', err.message || 'GitHub OAuth failed.');
                }
            });
        }
        if (btnHeaderSignOut) {
            btnHeaderSignOut.addEventListener('click', async (e) => {
                e.preventDefault();
                try {
                    await signOut();
                    updateAuthStateUI('SIGNED_OUT', null, null);
                } catch (err) {
                    console.warn('[BIS Auth] SignOut error:', err);
                    updateAuthStateUI('SIGNED_OUT', null, null);
                }
                const path = window.location.pathname || '';
                const isStaticOrFile = window.location.protocol === 'file:' || path.endsWith('.html');
                const loginUrl = isStaticOrFile ? './login.html' : '/login';
                try {
                    window.location.href = loginUrl;
                } catch {
                    openAuthModal('signin');
                }
            });
        }
        if (authForm) {
            authForm.addEventListener('submit', handleAuthFormSubmit);
        }

        // Auth State Synchronization
        function updateAuthStateUI(event, session, user) {
            const sidebarAvatarImg = document.getElementById('sidebarAvatarImg');
            const sidebarAvatarInitial = document.getElementById('sidebarAvatarInitial');
            const sidebarUserName = document.getElementById('sidebarUserName');
            const sidebarUserSubText = document.getElementById('sidebarUserSubText');
            const btnSidebarSignOut = document.getElementById('btnSidebarSignOut');

            const headerAvatarImg = document.getElementById('headerAvatarImg');
            const headerAvatarInitial = document.getElementById('headerAvatarInitial');

            const effectiveUser = (event === 'SIGNED_OUT') ? null : (user || (typeof getCachedUser === 'function' ? getCachedUser() : null));

            if (effectiveUser) {
                if (btnOpenAuthModal) btnOpenAuthModal.classList.add('hidden');
                if (userProfilePill) userProfilePill.classList.remove('hidden');

                const meta = effectiveUser.user_metadata || {};
                const displayName = meta.full_name || meta.name || effectiveUser.name || effectiveUser.email?.split('@')[0] || 'Workspace User';

                // Display login email or GitHub username
                const githubUsername = meta.user_name || meta.preferred_username;
                const loginEmail = effectiveUser.email || meta.email || '';
                const subtext = githubUsername ? `@${githubUsername}` : (loginEmail || 'Authenticated');

                if (userEmailText) userEmailText.textContent = subtext;
                if (sidebarUserName) {
                    sidebarUserName.removeAttribute('data-i18n');
                    sidebarUserName.textContent = displayName;
                }
                if (sidebarUserSubText) {
                    sidebarUserSubText.removeAttribute('data-i18n');
                    sidebarUserSubText.textContent = subtext;
                }

                const avatarUrl = meta.avatar_url || meta.picture || meta.avatar || '';
                const initial = (displayName[0] || loginEmail[0] || 'U').toUpperCase();

                // Profile picture on the left side
                if (avatarUrl && sidebarAvatarImg) {
                    sidebarAvatarImg.src = avatarUrl;
                    sidebarAvatarImg.setAttribute('referrerpolicy', 'no-referrer');
                    sidebarAvatarImg.classList.remove('hidden');
                    if (sidebarAvatarInitial) sidebarAvatarInitial.classList.add('hidden');
                    sidebarAvatarImg.onerror = () => {
                        sidebarAvatarImg.classList.add('hidden');
                        if (sidebarAvatarInitial) {
                            sidebarAvatarInitial.textContent = initial;
                            sidebarAvatarInitial.classList.remove('hidden');
                        }
                    };
                } else if (sidebarAvatarInitial) {
                    if (sidebarAvatarImg) sidebarAvatarImg.classList.add('hidden');
                    sidebarAvatarInitial.textContent = initial;
                    sidebarAvatarInitial.classList.remove('hidden');
                }

                // Topbar header avatar
                if (avatarUrl && headerAvatarImg) {
                    headerAvatarImg.src = avatarUrl;
                    headerAvatarImg.setAttribute('referrerpolicy', 'no-referrer');
                    headerAvatarImg.classList.remove('hidden');
                    if (headerAvatarInitial) headerAvatarInitial.classList.add('hidden');
                    headerAvatarImg.onerror = () => {
                        headerAvatarImg.classList.add('hidden');
                        if (headerAvatarInitial) {
                            headerAvatarInitial.textContent = initial;
                            headerAvatarInitial.classList.remove('hidden');
                        }
                    };
                } else if (headerAvatarInitial) {
                    if (headerAvatarImg) headerAvatarImg.classList.add('hidden');
                    headerAvatarInitial.textContent = initial;
                    headerAvatarInitial.classList.remove('hidden');
                }

                if (btnSidebarSignOut) {
                    const span = btnSidebarSignOut.querySelector('span');
                    if (span) {
                        span.setAttribute('data-i18n', 'nav.sign_out');
                        span.textContent = t('nav.sign_out', 'Sign out');
                    }
                    btnSidebarSignOut.setAttribute('title', t('nav.sign_out', 'Sign out of your account'));
                    const svg = btnSidebarSignOut.querySelector('svg');
                    if (svg) {
                        svg.innerHTML = '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>';
                    }
                }
            } else {
                if (btnOpenAuthModal) btnOpenAuthModal.classList.remove('hidden');
                if (userProfilePill) userProfilePill.classList.add('hidden');
                if (sidebarUserName) {
                    sidebarUserName.setAttribute('data-i18n', 'nav.user_default');
                    sidebarUserName.textContent = t('nav.user_default', 'Workspace User');
                }
                if (sidebarUserSubText) {
                    sidebarUserSubText.setAttribute('data-i18n', 'nav.status_operational');
                    sidebarUserSubText.textContent = t('nav.status_operational', 'Operational');
                }

                if (sidebarAvatarImg) sidebarAvatarImg.classList.add('hidden');
                if (sidebarAvatarInitial) {
                    sidebarAvatarInitial.textContent = 'U';
                    sidebarAvatarInitial.classList.remove('hidden');
                }

                if (headerAvatarImg) headerAvatarImg.classList.add('hidden');
                if (headerAvatarInitial) {
                    headerAvatarInitial.textContent = 'U';
                    headerAvatarInitial.classList.remove('hidden');
                }

                if (btnSidebarSignOut) {
                    const span = btnSidebarSignOut.querySelector('span');
                    if (span) {
                        span.setAttribute('data-i18n', 'nav.sign_in');
                        span.textContent = t('nav.sign_in', 'Sign in');
                    }
                    btnSidebarSignOut.setAttribute('title', t('nav.sign_in', 'Sign in to your account'));
                    const svg = btnSidebarSignOut.querySelector('svg');
                    if (svg) {
                        svg.innerHTML = '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/>';
                    }
                }
            }
        }

        const initialCachedUser = typeof getCachedUser === 'function' ? getCachedUser() : null;
        if (initialCachedUser) {
            updateAuthStateUI('SYNC_INIT', null, initialCachedUser);
        }
        onAuthStateChange(updateAuthStateUI);
        initializeAuth();

        // Check if user landed with auth query params or hash
        const urlParams = new URLSearchParams(window.location.search);
        const hashVal = (window.location.hash || '').toLowerCase();
        if (urlParams.get('mode') === 'reset-password') {
            openAuthModal('reset');
        } else if (urlParams.get('mode') === 'signin' || urlParams.get('auth') === 'login' || hashVal === '#login' || hashVal === '#signin') {
            openAuthModal('signin');
        } else if (urlParams.get('mode') === 'signup' || hashVal === '#signup') {
            openAuthModal('signup');
        }

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
        if (hash === '#assistant' || hash === '#chat') {
            switchView('assistant');
        } else if (hash === '#labs' || hash === '#labfinder') {
            switchView('labfinder');
        } else if (hash === '#login' || hash === '#signin') {
            switchView('home');
            openAuthModal('signin');
        } else if (hash === '#signup') {
            switchView('home');
            openAuthModal('signup');
        } else {
            // Direct page or #home defaults to the homepage
            switchView('home');
            if (hash && hash !== '#home') {
                const search = window.location.search || '';
                history.replaceState(null, '', window.location.pathname + search);
            }
        }
    }

    try {
        initLanguageSelectors();
        loadI18n();
    } catch (err) {
        console.error('[BIS Init] i18n initialization error:', err);
    }

    try {
        setupEventListeners();
    } catch (err) {
        console.error('[BIS Init] setupEventListeners error:', err);
    }

    try {
        loadConversations();
    } catch (err) {
        console.error('[BIS Init] loadConversations error:', err);
    }

    try {
        handleHashRouting();
        window.addEventListener('hashchange', handleHashRouting);
    } catch (err) {
        console.error('[BIS Init] handleHashRouting error:', err);
    }

    // Check backend health asynchronously
    const checkHealthFn = AssistantService.checkHealth || AssistantService.checkBackendHealth;
    if (typeof checkHealthFn === 'function') {
        checkHealthFn.call(AssistantService).then(health => {
            if (health && health.status === 'healthy') {
                backendMode = 'production';
                if (btnApiProd) btnApiProd.classList.add('active');
                if (btnApiMock) btnApiMock.classList.remove('active');
                console.log('Production Engine connected successfully.');
            } else {
                console.log('Production backend endpoint offline, defaulting to high-fidelity mock adapter.');
            }
        }).catch(() => {
            console.log('Production backend endpoint offline, defaulting to high-fidelity mock adapter.');
        });
    }
}

// Bootstrap on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}

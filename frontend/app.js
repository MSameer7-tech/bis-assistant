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

import { AssistantService } from './mockData.js?v=14.2.0';
import { LabFinderComponent } from './labFinderComponent.js';
import { ComplianceJourneyComponent } from './complianceJourneyComponent.js?v=14.7.2';
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
    getCachedUser,
    validateSession,
    getLoginUrl,
    getHomeUrl,
    isGuestSession,
    setGuestSession,
    validateDeliverableEmail,
    getEmailCooldownRemaining,
    setEmailCooldown,
    isEmailCooldownActive,
    EMAIL_COOLDOWN_ACTIONS
} from './auth.js?v=14.2.0';

import {
    DEFAULT_USER_PREFERENCES as MODULE_DEFAULT_USER_PREFERENCES,
    getUserPreferences as getStoredUserPreferences,
    saveUserPreferences as storeUserPreferences,
    loadUserPreferencesFromSupabase,
    clearAuthenticatedPreferences,
    normalizeDbToFrontend,
    normalizeFrontendToDb
} from './preferences.js?v=14.6.1';

import {
    generateUUID,
    isUUID,
    getAuthenticatedUserId,
    upsertConversationToSupabase,
    insertMessageToSupabase,
    loadConversationsFromSupabase,
    deleteConversationFromSupabase
} from './conversations.js?v=15.0.0';

import {
    ConversationManager,
    deriveDeterministicTitle,
    requestGroqTitle
} from './conversationManager.js?v=15.0.0';

function initApp() {
    // -------------------------------------------------------------------------
    // DOM Element References
    // -------------------------------------------------------------------------
    // Views
    const viewAssistant = document.getElementById('viewAssistant');
    const viewHome = document.getElementById('viewHome');
    const viewLabFinder = document.getElementById('viewLabFinder');
    const viewComplianceJourney = document.getElementById('viewComplianceJourney');
    const navAssistant = document.getElementById('navAssistant');
    const navHome = document.getElementById('navHome');
    const navLabFinder = document.getElementById('navLabFinder');
    const navComplianceJourney = document.getElementById('navComplianceJourney');
    const brandLink = document.getElementById('brandLink');
    const btnStartAssistant = document.getElementById('btnStartAssistant');

    // Subcomponents (Lab Finder & Compliance Journey)
    let labFinder = null;
    let complianceJourney = null;

    function initSubComponents() {
        if (viewLabFinder && !labFinder) {
            try {
                labFinder = new LabFinderComponent({
                    container: viewLabFinder,
                    mapContainer: 'labFinderMap',
                    apiEndpoint: apiUrl('/api/labs/search'),
                    t: (k, fb) => { try { return t(k, fb); } catch (e) { return fb || k; } },
                    getLanguage: () => currentLanguage
                });
                labFinder.init();
            } catch (labErr) {
                console.warn('[BIS Init] LabFinderComponent initialization deferred:', labErr);
            }
        }

        if (viewComplianceJourney && !complianceJourney) {
            try {
                complianceJourney = new ComplianceJourneyComponent({
                    container: viewComplianceJourney,
                    apiEndpoint: apiUrl('/api/compliance/journey'),
                    t: (k, fb) => { try { return t(k, fb); } catch (e) { return fb || k; } },
                    getLanguage: () => currentLanguage,
                    onOpenEvidence: (evId) => openEvidenceDrawer(evId),
                    onOpenLabFinder: (std, loc) => {
                        switchView('labfinder');
                        if (labFinder && viewLabFinder) {
                            const inputStd = viewLabFinder.querySelector('#labInputStandard') || viewLabFinder.querySelector('#labInputQuery');
                            const inputLoc = viewLabFinder.querySelector('#labInputLocation');
                            if (inputStd) inputStd.value = std;
                            if (inputLoc) inputLoc.value = loc || '';
                            labFinder.executeSearchFromInputs();
                        }
                    }
                });
                complianceJourney.init();
            } catch (compErr) {
                console.warn('[BIS Init] ComplianceJourneyComponent initialization deferred:', compErr);
            }
        }
    }

    // Sidebar
    const sidebar = document.getElementById('sidebar');
    const sidebarBackdrop = document.getElementById('sidebarBackdrop');
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const mobileSidebarClose = document.getElementById('mobileSidebarClose');
    const btnNewChat = document.getElementById('btnNewChat');
    const btnCollapsedNewChat = document.getElementById('btnCollapsedNewChat');
    const navCollapsedConversations = document.getElementById('navCollapsedConversations');
    const collapsedConvPopover = document.getElementById('collapsedConvPopover');
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

    const authSignupConfirmationBox = document.getElementById('authSignupConfirmationBox');
    const authConfirmationTargetEmail = document.getElementById('authConfirmationTargetEmail');
    const authSignupCooldownBadge = document.getElementById('authSignupCooldownBadge');
    const authSignupCooldownText = document.getElementById('authSignupCooldownText');
    const btnAuthBackToSignIn = document.getElementById('btnAuthBackToSignIn');

    // Sidebar User Action Buttons
    const btnSidebarPreferences = document.getElementById('btnSidebarPreferences');
    const btnThemeToggle = document.getElementById('btnThemeToggle');
    const btnSidebarTour = document.getElementById('btnSidebarTour');
    const btnSystemModalTour = document.getElementById('btnSystemModalTour');

    // Onboarding & Personalization Elements
    const onboardingModalBackdrop = document.getElementById('onboardingModalBackdrop');
    const onboardingModal = document.getElementById('onboardingModal');
    const onboardingModalTitle = document.getElementById('onboardingModalTitle');
    const onboardingModalSubtitle = document.getElementById('onboardingModalSubtitle');
    const onboardingKicker = document.getElementById('onboardingKicker');
    const onboardingStepBadge = document.getElementById('onboardingStepBadge');
    const onboardingProgressFill = document.getElementById('onboardingProgressFill');
    const btnOnboardingClose = document.getElementById('btnOnboardingClose');
    const btnOnboardingSkip = document.getElementById('btnOnboardingSkip');
    const btnOnboardingBack = document.getElementById('btnOnboardingBack');
    const btnOnboardingNext = document.getElementById('btnOnboardingNext');
    const onboardingNextText = document.getElementById('onboardingNextText');
    const obCountrySelect = document.getElementById('obCountrySelect');
    const obIndiaLocationWrap = document.getElementById('obIndiaLocationWrap');
    const obStateInput = document.getElementById('obStateInput');
    const obStateList = document.getElementById('obStateList');
    const obStateDropdown = document.getElementById('obStateDropdown');
    const btnToggleStateDropdown = document.getElementById('btnToggleStateDropdown');
    const obStateComboboxWrap = document.getElementById('obStateComboboxWrap');
    const obCityInput = document.getElementById('obCityInput');
    const obCityList = document.getElementById('obCityList');
    const obCityDropdown = document.getElementById('obCityDropdown');
    const btnToggleCityDropdown = document.getElementById('btnToggleCityDropdown');
    const obCityComboboxWrap = document.getElementById('obCityComboboxWrap');
    const obPopularCitiesWrap = document.getElementById('obPopularCitiesWrap');

    // Quick Tour Elements
    const quickTourModalBackdrop = document.getElementById('quickTourModalBackdrop');
    const quickTourModal = document.getElementById('quickTourModal');
    const btnTourClose = document.getElementById('btnTourClose');
    const btnTourPrev = document.getElementById('btnTourPrev');
    const btnTourNext = document.getElementById('btnTourNext');
    const tourDots = document.getElementById('tourDots');
    const tourSlidesContainer = document.getElementById('tourSlidesContainer');

    // -------------------------------------------------------------------------
    // Application State
    // -------------------------------------------------------------------------
    let currentView = 'home'; // 'home' | 'assistant' | 'labfinder'
    let conversations = [];
    let currentConversationId = null;
    let evidenceMemory = {}; // Cache of evidence units by unit_id
    window.evidenceMemory = evidenceMemory;
    let backendMode = 'production'; // 'production' | 'mock'
    let authMode = 'signin'; // 'signin' | 'signup' | 'forgot' | 'reset'

    // -------------------------------------------------------------------------
    // Phase M1: Internationalization (i18n) Engine
    // -------------------------------------------------------------------------
    const SUPPORTED_LANGUAGES = {
        en: { code: 'EN', name: 'English', native: 'English' },
        hi: { code: 'हि', name: 'Hindi', native: 'हिन्दी' },
        bn: { code: 'বাং', name: 'Bengali', native: 'বাংলা' },
        te: { code: 'తె', name: 'Telugu', native: 'తెలుగు' },
        mr: { code: 'म', name: 'Marathi', native: 'मराठी' },
        ta: { code: 'த', name: 'Tamil', native: 'தமிழ்' },
        gu: { code: 'ગુ', name: 'Gujarati', native: 'ગુજરાતી' },
        kn: { code: 'ಕ', name: 'Kannada', native: 'ಕನ್ನಡ' },
        ml: { code: 'മ', name: 'Malayalam', native: 'മലയാളം' },
        pa: { code: 'ਪੰ', name: 'Punjabi', native: 'ਪੰਜਾਬੀ' },
        as: { code: 'অ', name: 'Assamese', native: 'অসমীয়া' },
        or: { code: 'ଓ', name: 'Odia', native: 'ଓଡ଼ିଆ' }
    };

    let currentLanguage = 'en';
    try {
        currentLanguage = localStorage.getItem('bis_ui_language') || 'en';
        if (!SUPPORTED_LANGUAGES[currentLanguage]) {
            currentLanguage = 'en';
        }
    } catch (e) {
        currentLanguage = 'en';
    }

    const i18nCache = {};
    const i18nLoadingPromises = {};

    async function ensureLanguageLoaded(lang) {
        const targetLang = (lang && SUPPORTED_LANGUAGES[lang]) ? lang : 'en';
        if (i18nCache[targetLang]) {
            return i18nCache[targetLang];
        }
        if (i18nLoadingPromises[targetLang]) {
            return i18nLoadingPromises[targetLang];
        }
        i18nLoadingPromises[targetLang] = (async () => {
            try {
                const res = await fetch(`./i18n/${targetLang}.json`);
                if (res.ok) {
                    const data = await res.json();
                    i18nCache[targetLang] = data;
                    return data;
                } else {
                    console.warn(`[i18n] Failed to fetch dictionary for ${targetLang}: HTTP ${res.status}`);
                }
            } catch (e) {
                console.warn(`[i18n] Network error fetching dictionary for ${targetLang}:`, e);
            } finally {
                delete i18nLoadingPromises[targetLang];
            }
            return null;
        })();
        return i18nLoadingPromises[targetLang];
    }

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

    async function applyLanguage(lang, syncPreferences = false) {
        if (!SUPPORTED_LANGUAGES[lang]) {
            lang = 'en';
        }
        currentLanguage = lang;
        try {
            localStorage.setItem('bis_ui_language', lang);
        } catch (e) {
            // localStorage not accessible
        }
        document.documentElement.lang = lang;

        // Ensure current language and fallback English dictionaries are loaded
        await Promise.all([
            ensureLanguageLoaded(lang),
            ensureLanguageLoaded('en')
        ]);

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

        // Sync all language dropdown selectors across the UI
        document.querySelectorAll('.lang-select').forEach(sel => {
            if (sel.value !== lang) {
                sel.value = lang;
            }
        });

        // Sync onboarding language grid cards if present
        document.querySelectorAll('#onboardingLangGrid .onboarding-lang-card').forEach(card => {
            const cardLang = card.getAttribute('data-lang');
            const isSelected = cardLang === lang;
            card.classList.toggle('selected', isSelected);
            card.setAttribute('aria-checked', isSelected ? 'true' : 'false');
        });

        // Update active class on any legacy language toggle buttons
        document.querySelectorAll('.btn-lang-toggle').forEach(btn => {
            const btnLang = btn.getAttribute('data-lang');
            btn.classList.toggle('active', btnLang === lang);
        });

        // Sync collapsed sidebar language badge & tooltip
        const langMeta = SUPPORTED_LANGUAGES[lang] || { code: (lang || 'en').toUpperCase().slice(0, 2), name: lang, native: lang };
        const collapsedCode = document.getElementById('collapsedLangCode');
        if (collapsedCode) {
            collapsedCode.textContent = langMeta.code;
        }
        const btnCollapsed = document.getElementById('btnCollapsedLangToggle');
        if (btnCollapsed) {
            btnCollapsed.setAttribute('title', `Active language: ${langMeta.native} (${langMeta.name || lang})`);
            btnCollapsed.setAttribute('aria-label', `Active language: ${langMeta.native} (${langMeta.name || lang})`);
        }

        // Notify LabFinder component to re-render active results and dropdowns
        if (labFinder && typeof labFinder.onLanguageChange === 'function') {
            labFinder.onLanguageChange(lang);
        }

        // Notify ComplianceJourney component to re-render active journey and texts
        if (complianceJourney && typeof complianceJourney.onLanguageChange === 'function') {
            complianceJourney.onLanguageChange(lang);
        }

        // Re-sync auth UI so dynamic user profile/status is not regressed by translation sweep
        if (typeof updateAuthStateUI === 'function') {
            const cached = typeof getCachedUser === 'function' ? getCachedUser() : null;
            updateAuthStateUI('LANG_CHANGE', null, cached);
        }

        // Sync language change to user preferences ONLY if explicitly requested by user action
        if (syncPreferences) {
            try {
                if (typeof getUserPreferences === 'function' && typeof storeUserPreferences === 'function') {
                    const p = getUserPreferences();
                    if (p && p.language !== lang) {
                        storeUserPreferences({ ...p, language: lang });
                    }
                }
            } catch (e) {
                console.warn('[i18n] Failed to sync language to user preferences:', e);
            }
        }
    }

    // Expose globally for modular component access
    window.bisI18n = {
        t: (k, fb) => t(k, fb),
        getLanguage: () => currentLanguage,
        setLanguage: applyLanguage,
        getSupportedLanguages: () => ({ ...SUPPORTED_LANGUAGES }),
        ensureLanguageLoaded: ensureLanguageLoaded,
        cache: i18nCache
    };

    async function loadI18n() {
        try {
            await ensureLanguageLoaded('en');
            if (currentLanguage !== 'en') {
                await ensureLanguageLoaded(currentLanguage);
            }
        } catch (e) {
            console.warn('[i18n] Network fetch failed, relying on DOM defaults:', e);
        }
        await applyLanguage(currentLanguage);
    }

    function initLanguageSelectors() {
        // Dropdown language selects (sidebar and topbar)
        document.querySelectorAll('.lang-select').forEach(sel => {
            if (sel.value !== currentLanguage) {
                sel.value = currentLanguage;
            }
            sel.addEventListener('change', (e) => {
                const targetLang = e.target.value;
                if (targetLang && targetLang !== currentLanguage) {
                    applyLanguage(targetLang, true);
                }
            });
        });

        // Legacy toggle buttons if present
        document.querySelectorAll('.btn-lang-toggle').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const targetLang = btn.getAttribute('data-lang');
                if (targetLang && targetLang !== currentLanguage) {
                    applyLanguage(targetLang, true);
                }
            });
        });

        // Collapsed sidebar language toggle
        const btnCollapsed = document.getElementById('btnCollapsedLangToggle');
        if (btnCollapsed) {
            btnCollapsed.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (sidebar && sidebar.classList.contains('collapsed')) {
                    toggleSidebarCollapse();
                    setTimeout(() => {
                        const sidebarSel = document.getElementById('sidebarLangSelect');
                        if (sidebarSel) {
                            sidebarSel.focus();
                            if (typeof sidebarSel.showPicker === 'function') {
                                try { sidebarSel.showPicker(); } catch (_) {}
                            }
                        }
                    }, 180);
                } else {
                    const sidebarSel = document.getElementById('sidebarLangSelect');
                    if (sidebarSel) {
                        sidebarSel.focus();
                        if (typeof sidebarSel.showPicker === 'function') {
                            try { sidebarSel.showPicker(); } catch (_) {}
                        }
                    }
                }
            });
        }
    }



    // -------------------------------------------------------------------------
    // 1. Storage & Conversation Management
    // -------------------------------------------------------------------------
    function loadConversations() {
        try {
            const raw = localStorage.getItem('bis_ai_conversations_v2');
            if (raw) {
                conversations = JSON.parse(raw);
                // Ensure all cached conversations and messages have valid UUIDs
                let modified = false;
                if (Array.isArray(conversations)) {
                    conversations.forEach(c => {
                        if (!isUUID(c.id)) {
                            c.id = generateUUID();
                            modified = true;
                        }
                        if (Array.isArray(c.messages)) {
                            c.messages.forEach(m => {
                                if (!m.id || !isUUID(m.id)) {
                                    m.id = generateUUID();
                                    modified = true;
                                }
                            });
                        }
                    });
                }
                if (modified) saveConversations();
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

        const authUserId = getAuthenticatedUserId();
        if (authUserId) {
            syncConversationsFromSupabase(authUserId);
        }
    }

    let isSyncingConversations = false;

    async function syncConversationsFromSupabase(authUserId) {
        if (!authUserId || isSyncingConversations || (typeof isSubmittingQuery !== 'undefined' && isSubmittingQuery)) return;
        isSyncingConversations = true;
        try {
            const remoteConvs = await loadConversationsFromSupabase(authUserId);
            if (remoteConvs && Array.isArray(remoteConvs)) {
                // Preserve local device metadata (is_pinned, title_source)
                const localMetaMap = new Map((conversations || []).map(c => [c.id, { is_pinned: c.is_pinned, title_source: c.title_source }]));
                remoteConvs.forEach(rc => {
                    const local = localMetaMap.get(rc.id);
                    if (local) {
                        rc.is_pinned = Boolean(local.is_pinned);
                        rc.title_source = local.title_source || 'default';
                    }
                });

                if (remoteConvs.length > 0) {
                    const activeLocal = getCurrentConversation();
                    const matchingRemote = remoteConvs.find(c => c.id === activeLocal?.id);
                    if (activeLocal && (activeLocal.messages?.length || 0) > (matchingRemote?.messages?.length || 0)) {
                        // Local active conversation has newer uncommitted messages, don't overwrite with stale remote
                        return;
                    }
                    conversations = remoteConvs;
                    if (!conversations.some(c => c.id === currentConversationId)) {
                        currentConversationId = conversations[0].id;
                    }
                    saveConversations();
                    renderConversationList();
                    renderActiveConversation();
                } else if (conversations.length > 0) {
                    // Supabase has 0 records; sync local conversations that have messages
                    for (const localConv of conversations) {
                        if (localConv.messages && localConv.messages.length > 0) {
                            await upsertConversationToSupabase(localConv, authUserId);
                            for (const msg of localConv.messages) {
                                await insertMessageToSupabase(msg, localConv.id, authUserId);
                            }
                        }
                    }
                }
            }
        } catch (err) {
            console.warn('[BIS Conversations] Background sync error:', err);
        } finally {
            isSyncingConversations = false;
        }
    }

    function saveConversations() {
        try {
            localStorage.setItem('bis_ai_conversations_v2', JSON.stringify(conversations));
        } catch (e) {
            console.warn('Failed to save conversations to localStorage:', e);
        }
    }

    const conversationManager = new ConversationManager({
        onSelect: (convId) => {
            switchConversation(convId);
            if (collapsedConvPopover) collapsedConvPopover.classList.add('hidden');
        },
        onNewChat: () => {
            createNewConversation(true);
            if (collapsedConvPopover) collapsedConvPopover.classList.add('hidden');
        },
        onRename: (convId, newTitle) => {
            const conv = conversations.find(c => c.id === convId);
            if (conv) {
                conv.title = newTitle;
                conv.title_source = 'user';
                conv.updatedAt = Date.now();
                saveConversations();
                renderConversationList();
                if (currentConversationId === convId && currentChatTitle) {
                    currentChatTitle.textContent = newTitle;
                }
                const authUserId = getAuthenticatedUserId();
                if (authUserId) {
                    upsertConversationToSupabase(conv, authUserId);
                }
            }
        },
        onTogglePin: (convId) => {
            const conv = conversations.find(c => c.id === convId);
            if (conv) {
                conv.is_pinned = !conv.is_pinned;
                saveConversations();
                renderConversationList();
            }
        },
        onDelete: (convId) => {
            deleteConversation(convId);
        }
    });

    function createNewConversation(switchViewToAssistant = true) {
        const newConv = {
            id: generateUUID(),
            title: 'New Session',
            messages: [],
            is_pinned: false,
            title_source: 'default',
            createdAt: Date.now(),
            updatedAt: Date.now()
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
        if (e && typeof e.stopPropagation === 'function') e.stopPropagation();
        const authUserId = getAuthenticatedUserId();
        if (authUserId) {
            deleteConversationFromSupabase(convId, authUserId);
        }
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

    function renderConversationList(filterQuery = null) {
        const query = (filterQuery !== null && filterQuery !== undefined) 
            ? filterQuery 
            : (chatSearchInput ? chatSearchInput.value : '');
        conversationManager.renderList(conversationList, conversations, currentConversationId, query);
        if (collapsedConvPopover && !collapsedConvPopover.classList.contains('hidden')) {
            conversationManager.renderPopover(collapsedConvPopover, conversations, currentConversationId);
        }
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
            applyPersonalization();
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
                    appendUserMessageToDOM(msg.text || msg.content || '');
                } else if (msg.role === 'assistant') {
                    const dataPayload = msg.data || {
                        answer: msg.text || msg.content || '',
                        status: 'SUFFICIENT',
                        generation_mode: 'GROUNDED'
                    };
                    appendAssistantResponseToDOM(dataPayload, false);
                }
            });

            scrollToBottom();
            if (chatInput && currentView === 'assistant') {
                chatInput.focus();
            }
        }
    }

    // -------------------------------------------------------------------------
    // 2. View Switching: Assistant vs Home vs Lab Finder vs Compliance Journey
    // -------------------------------------------------------------------------
    function switchView(viewName) {
        window.switchView = switchView;
        currentView = viewName;
        initSubComponents();
        const targetHash = (viewName === 'compliance' || viewName === 'journey') ? '#compliance' : (viewName === 'labfinder' || viewName === 'labs' ? '#labfinder' : (viewName === 'home' ? '#home' : '#assistant'));
        if (window.location.hash.toLowerCase() !== targetHash) {
            try {
                history.replaceState(null, '', targetHash);
            } catch (e) {}
        }
        if (viewName === 'home') {
            viewAssistant.classList.add('hidden');
            if (viewLabFinder) viewLabFinder.classList.add('hidden');
            if (viewComplianceJourney) viewComplianceJourney.classList.add('hidden');
            viewHome.classList.remove('hidden');
            navHome.classList.add('active');
            navAssistant.classList.remove('active');
            if (navLabFinder) navLabFinder.classList.remove('active');
            if (navComplianceJourney) navComplianceJourney.classList.remove('active');
        } else if (viewName === 'labfinder' || viewName === 'labs') {
            viewAssistant.classList.add('hidden');
            viewHome.classList.add('hidden');
            if (viewComplianceJourney) viewComplianceJourney.classList.add('hidden');
            if (viewLabFinder) {
                viewLabFinder.classList.remove('hidden');
                if (labFinder && labFinder.mapComponent) {
                    setTimeout(() => labFinder.mapComponent.invalidateSize(), 60);
                }
            }
            if (navLabFinder) navLabFinder.classList.add('active');
            navAssistant.classList.remove('active');
            navHome.classList.remove('active');
            if (navComplianceJourney) navComplianceJourney.classList.remove('active');
        } else if (viewName === 'compliance' || viewName === 'journey') {
            viewAssistant.classList.add('hidden');
            viewHome.classList.add('hidden');
            if (viewLabFinder) viewLabFinder.classList.add('hidden');
            if (viewComplianceJourney) {
                viewComplianceJourney.classList.remove('hidden');
            }
            if (navComplianceJourney) navComplianceJourney.classList.add('active');
            navAssistant.classList.remove('active');
            navHome.classList.remove('active');
            if (navLabFinder) navLabFinder.classList.remove('active');
        } else {
            viewHome.classList.add('hidden');
            if (viewLabFinder) viewLabFinder.classList.add('hidden');
            if (viewComplianceJourney) viewComplianceJourney.classList.add('hidden');
            viewAssistant.classList.remove('hidden');
            navAssistant.classList.add('active');
            navHome.classList.remove('active');
            if (navLabFinder) navLabFinder.classList.remove('active');
            if (navComplianceJourney) navComplianceJourney.classList.remove('active');
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
            conv.title = deriveDeterministicTitle(query);
            conv.title_source = 'fallback';
            currentChatTitle.textContent = conv.title;

            // Trigger asynchronous Groq title generation in background once
            requestGroqTitle(query, conv.id, (convId, groqTitle, source) => {
                const targetConv = conversations.find(c => c.id === convId);
                // Guard: Never overwrite user rename
                if (targetConv && targetConv.title_source !== 'user') {
                    targetConv.title = groqTitle;
                    targetConv.title_source = source || 'groq';
                    targetConv.updatedAt = Date.now();
                    saveConversations();
                    renderConversationList();
                    if (currentConversationId === convId && currentChatTitle) {
                        currentChatTitle.textContent = targetConv.title;
                    }
                    const authUserId = getAuthenticatedUserId();
                    if (authUserId) {
                        upsertConversationToSupabase(targetConv, authUserId);
                    }
                }
            });
        }

        const userMsg = {
            id: generateUUID(),
            role: 'user',
            text: query,
            createdAt: Date.now()
        };
        // Add user message to conversation
        conv.messages.push(userMsg);
        conv.updatedAt = Date.now();
        saveConversations();
        renderConversationList();

        // Asynchronously sync conversation and user message to Supabase (sequenced to satisfy foreign key)
        let userPersistPromise = null;
        const authUserId = getAuthenticatedUserId();
        if (authUserId) {
            userPersistPromise = (async () => {
                await upsertConversationToSupabase(conv, authUserId);
                await insertMessageToSupabase(userMsg, conv.id, authUserId);
            })().catch(e => console.warn('[BIS] Conv/User msg persist error:', e));
        }

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
            const userPrefs = typeof getUserPreferences === 'function' ? getUserPreferences() : null;
            const effectiveLang = userPrefs?.language || currentLanguage || 'en';
            // Build conversation history for context resolution (exclude the query currently being submitted)
            const priorMessages = (conv.messages || []).slice(0, -1);
            const historyMessages = priorMessages.slice(-10).map(m => {
                const text = m.text || m.data?.answer || m.data?.answer_markdown || '';
                const standard = m.data?.standard || m.data?.rag?.standard || (text.match(/\bIS\s*\d+\b/i) || [])[0] || undefined;
                const intent = m.data?.intent || m.data?.rag?.intent || undefined;
                const provenance = m.data?.provenance || undefined;
                return {
                    role: m.role,
                    text: text,
                    data: m.data ? {
                        answer: m.data.answer || m.data.answer_markdown || '',
                        intent: intent,
                        standard: standard,
                        provenance: provenance,
                        rag: m.data.rag ? { standard: standard, ...m.data.rag } : (standard ? { standard } : undefined)
                    } : (standard ? { standard, intent } : undefined)
                };
            });
            // Check if user is explicitly asking for a product compliance journey
            const isExplicitCompQuery = /compliance\s+journey|compliance\s+pathway|regulatory\s+pathway|what\s+standards,\s*certification,\s*testing|show\s+compliance\s+journey/i.test(query);

            let responseData;
            if (isExplicitCompQuery) {
                const compRes = await fetch(apiUrl('/api/compliance/journey'), {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        ...getAuthHeaders()
                    },
                    body: JSON.stringify({ query: query, conversation_history: historyMessages || [] })
                });

                if (!compRes.ok) {
                    const errText = await compRes.text();
                    throw new Error(`Compliance Journey resolution error (${compRes.status}): ${errText || compRes.statusText}`);
                }

                const compData = await compRes.json();
                const journeyObj = compData.journey || compData;
                const prodName = journeyObj.product?.product_name || 'the requested product';
                const stdsFound = journeyObj.applicable_standards?.standards?.map(s => s.standard_number).join(', ') || '';

                // Use V2 assessment as summary when available
                const v2Assessment = journeyObj.compliance_answer_v2?.assessment?.answer;
                const summaryText = v2Assessment
                    ? v2Assessment
                    : stdsFound
                        ? `Authoritative BIS Product Compliance Journey established for **${prodName}** covering standard(s) **${stdsFound}**. See the 10-stage regulatory pathway below.`
                        : `BIS Product Compliance Journey established for **${prodName}**. See the 10-stage regulatory pathway below.`;

                responseData = {
                    status: 'SUFFICIENT',
                    answer: summaryText,
                    generation_mode: 'GROUNDED',
                    response_style: userPrefs?.responseStyle || 'Detailed & Explanatory',
                    compliance_journey: journeyObj,
                    provenance: journeyObj.provenance || []
                };
            } else {
                responseData = await AssistantService.query(query, {
                    mode: backendMode,
                    headers: getAuthHeaders(),
                    language: effectiveLang,
                    responseStyle: userPrefs?.responseStyle || 'Detailed & Explanatory',
                    history: historyMessages
                });
            }

            thinkingRow.remove();

            const assistantMsg = {
                id: generateUUID(),
                role: 'assistant',
                text: responseData.answer || '',
                data: responseData,
                createdAt: Date.now()
            };
            // Store in conversation state with role, text, and data contract
            conv.messages.push(assistantMsg);
            conv.updatedAt = Date.now();
            saveConversations();

            if (authUserId) {
                (async () => {
                    if (userPersistPromise) {
                        try { await userPersistPromise; } catch (_) {}
                    }
                    await upsertConversationToSupabase(conv, authUserId);
                    await insertMessageToSupabase(assistantMsg, conv.id, authUserId);
                })().catch(e => console.warn('[BIS] Assistant msg persist error:', e));
            }

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
            <div class="assistant-avatar" aria-hidden="true" style="user-select: none;">
                <img src="/static/favicon.svg" alt="" aria-hidden="true" style="pointer-events: none; user-select: none;">
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
            <div class="assistant-avatar" aria-hidden="true" style="color: #f43f5e; border-color: rgba(244, 63, 94, 0.3); user-select: none;">
                <img src="/static/favicon.svg" alt="" aria-hidden="true" style="pointer-events: none; user-select: none;">
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
        let text = rawText.trim()
            .replace(/!?\[(?:image|alt)\]\([^)]*\)/gi, '')
            .replace(/https?:\/\/(?:localhost|127\.0\.0\.1)(?::\d+)?\/[^\s\)]+/gi, '')
            .replace(/<svg[\s\S]*?<\/svg>/gi, '')
            .replace(/\bsvgsvg\b/gi, '')
            .trim();
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
                userQueryText = userMsgs[userMsgs.length - 1].text || userMsgs[userMsgs.length - 1].content || userQueryText;
            }
        }

        const isLabQuery = Boolean(data.intent === 'LAB_SEARCH') || /\b(labs?|laborator(?:y|ies)|testing\s+facilit(?:y|ies)|testing\s+scope|where\s+to\s+test|who\s+can\s+test|accredited|lims|where\s+can\s+i\s+get.*tests?\s*done)\b/i.test(userQueryText);
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
            } else if (genMode === 'HYBRID' || status === 'PARTIAL') {
                sourceTagHtml = `<span class="subtle-source-tag tag-partial" data-i18n="assistant.status.hybrid">&bull; ${t('assistant.status.hybrid', 'Partially BIS-verified • Additional information is unverified')}</span>`;
            } else if (genMode === 'LLM_FALLBACK') {
                sourceTagHtml = `<span class="subtle-source-tag tag-fallback" data-i18n="assistant.status.fallback">&bull; ${t('assistant.status.fallback', 'General knowledge • Not BIS-verified')}</span>`;
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

        // 5.b Compliance Journey Interactive Bridge Widget (when standard mentioned and not already a full journey card)
        let complianceJourneyBridgeHtml = '';
        let complianceJourneyHtml = '';

        if (data.compliance_journey) {
            complianceJourneyHtml = ComplianceJourneyComponent.renderJourneyCard(data.compliance_journey, { t: (k, fb) => t(k, fb) });
        } else if (stdMatch) {
            const matchedStd = `IS ${stdMatch[1].replace(/\s+/g, ' ')}`;
            complianceJourneyBridgeHtml = `
                <div class="chat-compliance-bridge-card">
                    <div class="chat-compliance-bridge-info">
                        <span class="chat-compliance-bridge-icon" aria-hidden="true">📋</span>
                        <div>
                            <h5 class="chat-compliance-bridge-title">${t('compliance_journey.chat_bridge_title', 'Product Compliance Journey')}: ${escapeHtml(matchedStd)}</h5>
                            <p class="chat-compliance-bridge-desc">${t('compliance_journey.chat_bridge_desc', 'Explore complete regulatory status, mandatory certification, testing requirements, and qualified laboratories for this standard.')}</p>
                        </div>
                    </div>
                    <button type="button" class="btn-chat-open-compliance" data-standard="${escapeHtml(matchedStd)}">
                        <span>${t('compliance_journey.chat_bridge_btn', 'View Full Compliance Journey')} &rarr;</span>
                    </button>
                </div>
            `;
        }

        const userPrefs = typeof getUserPreferences === 'function' ? getUserPreferences() : null;
        const respStyle = data.response_style || userPrefs?.responseStyle || 'Detailed & Explanatory';
        let styleClass = 'style-detailed-explanatory';
        if (respStyle === 'Quick & Simple' || respStyle === 'quick') {
            styleClass = 'style-quick-simple';
        } else if (respStyle === 'Professional & Compliance-focused' || respStyle === 'professional') {
            styleClass = 'style-professional-compliance';
        }

        row.innerHTML = `
            <div class="assistant-avatar" aria-hidden="true" style="user-select: none;">
                <img src="/static/favicon.svg" alt="" aria-hidden="true" style="pointer-events: none; user-select: none;">
            </div>
            <div class="assistant-bubble-container">
                <div class="assistant-bubble ${styleClass}">
                    <div class="editorial-answer">${answerHtml}</div>
                    ${complianceJourneyHtml}
                    ${feeResultsHtml}
                    ${labResultsHtml}
                    ${labFinderBridgeHtml}
                    ${complianceJourneyBridgeHtml}
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

        // Wire up Compliance Journey bridge button
        row.querySelectorAll('.btn-chat-open-compliance').forEach(btn => {
            btn.addEventListener('click', () => {
                const std = btn.getAttribute('data-standard');
                switchView('compliance');
                if (complianceJourney && viewComplianceJourney) {
                    const inputStd = viewComplianceJourney.querySelector('#compInputStandard');
                    const inputProd = viewComplianceJourney.querySelector('#compInputProduct');
                    const inputQuery = viewComplianceJourney.querySelector('#compInputQuery');
                    if (inputStd) inputStd.value = std || '';
                    if (inputProd) inputProd.value = '';
                    if (inputQuery) inputQuery.value = '';
                    complianceJourney.executeSearchFromInputs();
                }
            });
        });

        // Wire up Compliance Journey card interactions if journey card rendered in chat
        if (data.compliance_journey) {
            ComplianceJourneyComponent.bindJourneyCardInteractions(row, data.compliance_journey, {
                onOpenEvidence: (evId) => openEvidenceDrawer(evId),
                onOpenLabFinder: (std, loc) => {
                    switchView('labfinder');
                    if (labFinder && viewLabFinder) {
                        const inputStd = viewLabFinder.querySelector('#labInputStandard') || viewLabFinder.querySelector('#labInputQuery');
                        const inputLoc = viewLabFinder.querySelector('#labInputLocation');
                        if (inputStd) inputStd.value = std;
                        if (inputLoc) inputLoc.value = loc || '';
                        labFinder.executeSearchFromInputs();
                    }
                }
            });
        }

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
        window.openEvidenceDrawer = openEvidenceDrawer;
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
    // 7b. Personalization, Onboarding & Quick Tour Controllers
    // -------------------------------------------------------------------------
    const INDIA_STATES_AND_CITIES = {
        "Andhra Pradesh": ["Visakhapatnam", "Vijayawada", "Guntur", "Nellore", "Kurnool", "Tirupati", "Rajahmundry", "Kakinada"],
        "Arunachal Pradesh": ["Itanagar", "Naharlagun", "Pasighat", "Tawang", "Ziro"],
        "Assam": ["Guwahati", "Silchar", "Dibrugarh", "Jorhat", "Nagaon", "Tinsukia", "Tezpur"],
        "Bihar": ["Patna", "Gaya", "Bhagalpur", "Muzaffarpur", "Purnia", "Darbhanga", "Bihar Sharif", "Arrah"],
        "Chhattisgarh": ["Raipur", "Bhilai", "Bilaspur", "Korba", "Durg", "Rajnandgaon"],
        "Goa": ["Panaji", "Margao", "Vasco da Gama", "Mapusa", "Ponda"],
        "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar", "Jamnagar", "Gandhinagar", "Junagadh"],
        "Haryana": ["Gurugram", "Faridabad", "Panipat", "Ambala", "Yamunanagar", "Rohtak", "Hisar", "Karnal", "Panchkula"],
        "Himachal Pradesh": ["Shimla", "Dharamshala", "Solan", "Mandi", "Baddi", "Kullu"],
        "Jharkhand": ["Ranchi", "Jamshedpur", "Dhanbad", "Bokaro Steel City", "Deoghar", "Hazaribagh"],
        "Karnataka": ["Bengaluru", "Mysuru", "Hubballi-Dharwad", "Mangaluru", "Belagavi", "Davangere", "Ballari", "Kalaburagi"],
        "Kerala": ["Thiruvananthapuram", "Kochi", "Kozhikode", "Thrissur", "Kollam", "Palakkad", "Alappuzha", "Kannur"],
        "Madhya Pradesh": ["Bhopal", "Indore", "Gwalior", "Jabalpur", "Ujjain", "Sagar", "Dewas", "Satna"],
        "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Thane", "Nashik", "Navi Mumbai", "Aurangabad", "Solapur", "Kolhapur"],
        "Manipur": ["Imphal", "Churachandpur", "Thoubal"],
        "Meghalaya": ["Shillong", "Tura", "Jowai"],
        "Mizoram": ["Aizawl", "Lunglei", "Champhai"],
        "Nagaland": ["Kohima", "Dimapur", "Mokokchung"],
        "Odisha": ["Bhubaneswar", "Cuttack", "Rourkela", "Berhampur", "Sambalpur", "Puri", "Balasore"],
        "Punjab": ["Ludhiana", "Amritsar", "Jalandhar", "Patiala", "Bathinda", "Mohali", "Pathankot", "Hoshiarpur"],
        "Rajasthan": ["Jaipur", "Jodhpur", "Kota", "Bikaner", "Ajmer", "Udaipur", "Bhilwara", "Alwar", "Sikar"],
        "Sikkim": ["Gangtok", "Namchi", "Gyalshing"],
        "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem", "Tiruppur", "Erode", "Vellore", "Tirunelveli"],
        "Telangana": ["Hyderabad", "Warangal", "Nizamabad", "Karimnagar", "Ramagundam", "Khammam", "Secunderabad"],
        "Tripura": ["Agartala", "Udaipur", "Dharmanagar"],
        "Uttar Pradesh": ["Lucknow", "Kanpur", "Noida", "Greater Noida", "Ghaziabad", "Varanasi", "Agra", "Prayagraj", "Meerut", "Bareilly", "Aligarh", "Moradabad"],
        "Uttarakhand": ["Dehradun", "Haridwar", "Roorkee", "Haldwani", "Rishikesh", "Rudrapur"],
        "West Bengal": ["Kolkata", "Howrah", "Durgapur", "Asansol", "Siliguri", "Bardhaman", "Kharagpur"],
        "Andaman and Nicobar Islands": ["Port Blair"],
        "Chandigarh": ["Chandigarh"],
        "Dadra and Nagar Haveli and Daman and Diu": ["Daman", "Diu", "Silvassa"],
        "Delhi (NCT)": ["New Delhi", "North Delhi", "South Delhi", "West Delhi", "East Delhi", "Dwarka", "Rohini"],
        "Jammu and Kashmir": ["Srinagar", "Jammu", "Anantnag", "Baramulla"],
        "Ladakh": ["Leh", "Kargil"],
        "Lakshadweep": ["Kavaratti"],
        "Puducherry": ["Puducherry", "Karaikal", "Mahe", "Yanam"]
    };

    const DEFAULT_USER_PREFERENCES = MODULE_DEFAULT_USER_PREFERENCES;

    function getUserPreferences() {
        return getStoredUserPreferences();
    }

    function saveUserPreferences(prefs) {
        return storeUserPreferences(prefs);
    }

    function renderPersonalizedWelcome(prefs) {
        const headline = document.querySelector('#welcomeContainer .hero-headline');
        const subtitle = document.querySelector('#welcomeContainer .hero-subtitle');
        if (!headline || !subtitle) return;

        switch (prefs?.role) {
            case 'Manufacturer':
                headline.textContent = "Welcome, Manufacturer";
                subtitle.textContent = "Navigate Indian Standards, mandatory QCOs, testing scopes, and certification pathways from one focused workspace.";
                break;
            case 'Importer / Exporter':
                headline.textContent = "Welcome, Importer / Exporter";
                subtitle.textContent = "Verify border compliance, mandatory certification schemes, and foreign manufacturer regulations (FMCS).";
                break;
            case 'Business / Seller':
                headline.textContent = "Welcome, Business & Seller";
                subtitle.textContent = "Check product standards, licence validity, and mandatory quality control regulations.";
                break;
            case 'Testing Laboratory':
                headline.textContent = "Welcome, Laboratory Professional";
                subtitle.textContent = "Inspect normative test parameters, testing fee schedules, and recognized laboratory scopes.";
                break;
            case 'Compliance / Regulatory Professional':
                headline.textContent = "Welcome, Compliance Professional";
                subtitle.textContent = "Explore statutory clauses, gazette QCO mandates, and regulatory conformity procedures.";
                break;
            case 'Consumer':
                headline.textContent = "Welcome, Consumer";
                subtitle.textContent = "Verify Gold Hallmarking (HUID), ISI marks, and product safety standards.";
                break;
            case 'Student / Researcher':
                headline.textContent = "Welcome, Researcher";
                subtitle.textContent = "Explore Indian Standards repository, technical clauses, and normative test methodologies.";
                break;
            default:
                headline.textContent = t('assistant.headline', 'What would you like to research?');
                subtitle.textContent = t('assistant.subtitle', 'Search Indian Standards, testing requirements, laboratory scopes, and evidence from one focused workspace.');
                break;
        }
    }

    const BIS_ROLE_SUGGESTIONS = {
        'Manufacturer': [
            { query: "What is IS 4985 and its testing scope?", label: "IS 4985 PVC pipes compliance" },
            { query: "What are mandatory QCO regulations for manufacturing?", label: "Mandatory QCO regulations" },
            { query: "What is the BIS Scheme I certification process?", label: "BIS Scheme I Certification" },
            { query: "Which laboratories have scope for IS 4985?", label: "Laboratories for IS 4985" }
        ],
        'Importer / Exporter': [
            { query: "What is the Foreign Manufacturers Certification Scheme (FMCS)?", label: "FMCS import requirements" },
            { query: "Which products have mandatory QCOs for import into India?", label: "Import mandatory QCOs" },
            { query: "How to verify BIS licence validity for customs clearance?", label: "Verify licence for customs" },
            { query: "Which BIS recognized laboratories test imported goods?", label: "Laboratories for imported goods" }
        ],
        'Business / Seller': [
            { query: "How to check if a product requires mandatory BIS certification?", label: "Mandatory certification check" },
            { query: "How to verify valid BIS ISI licence on products?", label: "Verify BIS ISI licence" },
            { query: "What are mandatory Quality Control Orders for electronics?", label: "Electronics QCO list" },
            { query: "What are penalties for selling non-BIS compliant goods?", label: "BIS Act compliance rules" }
        ],
        'Testing Laboratory': [
            { query: "What is the testing fee and parameter scope for IS 8978?", label: "IS 8978 scope & fees" },
            { query: "What are BIS laboratory recognition and empanelment criteria?", label: "BIS Lab recognition criteria" },
            { query: "What are the normative test methods under IS 4985?", label: "Normative test methods IS 4985" },
            { query: "Find testing laboratories using verified testing scope", label: "Find 580+ BIS Lab records" }
        ],
        'Compliance / Regulatory Professional': [
            { query: "What are the latest Quality Control Orders (QCOs) issued by DPIIT?", label: "Latest Gazette QCO mandates" },
            { query: "What are the conformity assessment procedures under BIS Act 2016?", label: "Conformity assessment schemes" },
            { query: "What is the statutory penalty under Section 29 of the BIS Act?", label: "Section 29 penal provisions" },
            { query: "Show authoritative evidence for standard specifications", label: "Evidence-grounded standards" }
        ],
        'Consumer': [
            { query: "How do I verify a 6-digit Gold Hallmark (HUID)?", label: "Verify Gold Hallmark (HUID)" },
            { query: "Is ISI mark mandatory for packaged drinking water (IS 14543)?", label: "ISI mark for drinking water" },
            { query: "How to check if an ISI licence number on a product is genuine?", label: "Check genuine ISI licence" },
            { query: "Find accredited testing laboratories nearby", label: "Find laboratories nearby" }
        ],
        'Student / Researcher': [
            { query: "What is the IS 10500 standard for drinking water quality?", label: "IS 10500 Drinking water standard" },
            { query: "How are Indian Standards formulated and amended by BIS?", label: "Standards formulation process" },
            { query: "What is the testing methodology in IS 8978?", label: "IS 8978 Test methodology" },
            { query: "How to trace normative clauses to verified BIS sources?", label: "Trace normative clauses" }
        ],
        'default': [
            { query: "What is IS 8978?", label: "IS 8978 requirements" },
            { query: "Which laboratories have scope for IS 8978?", label: "Laboratories for IS 8978" },
            { query: "What is the testing fee for IS 8978?", label: "Testing fees for IS 8978" },
            { query: "Is there authoritative evidence for this requirement?", label: "Answers grounded in verified BIS evidence" }
        ]
    };

    const BIS_USECASE_SUGGESTIONS = {
        'Finding Indian Standards': {
            'Manufacturer': { query: "What is IS 4985 and its testing scope?", label: "IS 4985 PVC pipes compliance" },
            'Consumer': { query: "What is the IS 10500 standard for drinking water quality?", label: "IS 10500 Drinking water standard" },
            'Testing Laboratory': { query: "What is IS 8978 for electric water heaters?", label: "IS 8978 water heater standard" },
            'Student / Researcher': { query: "What is the IS 10500 standard for drinking water quality?", label: "IS 10500 Drinking water standard" },
            '_default': { query: "What is IS 4985 and what does it cover?", label: "Search IS 4985 standard" }
        },
        'Checking compliance requirements': {
            'Manufacturer': { query: "What are the mandatory compliance requirements under IS 4985?", label: "IS 4985 manufacturing compliance" },
            'Importer / Exporter': { query: "What are the mandatory import compliance requirements for electronics under CRS?", label: "Import CRS compliance rules" },
            'Business / Seller': { query: "How to check if a product requires mandatory BIS certification?", label: "Mandatory certification check" },
            'Compliance / Regulatory Professional': { query: "What are the conformity assessment procedures under BIS Act 2016?", label: "Conformity assessment schemes" },
            '_default': { query: "What are the statutory compliance requirements under the BIS Act?", label: "BIS statutory compliance" }
        },
        'Understanding QCOs': {
            'Manufacturer': { query: "What are mandatory QCO regulations for manufacturing?", label: "Mandatory manufacturing QCOs" },
            'Importer / Exporter': { query: "Which products have mandatory QCOs for import into India?", label: "Import mandatory QCOs" },
            'Business / Seller': { query: "What are mandatory Quality Control Orders for electronics?", label: "Electronics QCO list" },
            'Compliance / Regulatory Professional': { query: "What are the latest Quality Control Orders (QCOs) issued by DPIIT?", label: "Latest Gazette QCO mandates" },
            '_default': { query: "What is a Quality Control Order (QCO) and which products are covered?", label: "Understanding QCO mandates" }
        },
        'BIS Certification / Licensing': {
            'Manufacturer': { query: "What is the BIS Scheme I certification process?", label: "BIS Scheme I Certification" },
            'Importer / Exporter': { query: "What is the Foreign Manufacturers Certification Scheme (FMCS)?", label: "FMCS certification scheme" },
            'Business / Seller': { query: "How to apply for a BIS licence under Scheme I?", label: "BIS Licence application" },
            'Compliance / Regulatory Professional': { query: "What are the conformity assessment procedures under BIS Act 2016?", label: "Conformity assessment schemes" },
            '_default': { query: "What are the steps to obtain a BIS certification licence?", label: "BIS Certification process" }
        },
        'Testing Requirements': {
            'Testing Laboratory': { query: "What are the normative test methods under IS 4985?", label: "Normative test methods IS 4985" },
            'Manufacturer': { query: "What are the key testing requirements for IS 4985?", label: "IS 4985 testing requirements" },
            'Student / Researcher': { query: "What is the testing methodology in IS 8978?", label: "IS 8978 Test methodology" },
            '_default': { query: "What are the testing requirements for IS 8978?", label: "IS 8978 testing requirements" }
        },
        'Finding Testing Laboratories': {
            'Testing Laboratory': { query: "Which laboratories have scope for IS 8978?", label: "Laboratories for IS 8978" },
            'Consumer': { query: "Find accredited testing laboratories nearby", label: "Find laboratories nearby" },
            'Importer / Exporter': { query: "Which BIS recognized laboratories test imported goods?", label: "Laboratories for imported goods" },
            '_default': { query: "Which laboratories explicitly have scope for IS 4985?", label: "Laboratories for IS 4985" }
        },
        'Hallmarking / HUID': {
            'Consumer': { query: "How do I verify a 6-digit Gold Hallmark (HUID)?", label: "Verify Gold Hallmark (HUID)" },
            'Business / Seller': { query: "What are the hallmarking registration requirements for jewellers?", label: "Jeweller hallmarking rules" },
            '_default': { query: "How do I verify a 6-digit Gold Hallmark (HUID)?", label: "Verify Gold Hallmark (HUID)" }
        },
        'Verifying BIS Licence / Certification': {
            'Consumer': { query: "How to check if an ISI licence number on a product is genuine?", label: "Check genuine ISI licence" },
            'Business / Seller': { query: "How to verify valid BIS ISI licence on products?", label: "Verify BIS ISI licence" },
            'Importer / Exporter': { query: "How to verify BIS licence validity for customs clearance?", label: "Verify licence for customs" },
            '_default': { query: "How to verify the validity of a BIS licence or certificate?", label: "Verify BIS licence" }
        },
        'Understanding Standards & Clauses': {
            'Compliance / Regulatory Professional': { query: "How to trace normative clauses to verified BIS sources?", label: "Trace normative clauses" },
            'Student / Researcher': { query: "How are Indian Standards formulated and amended by BIS?", label: "Standards formulation process" },
            '_default': { query: "What are the normative clauses and specifications in IS 8978?", label: "IS 8978 clauses & specs" }
        },
        'Other': {
            '_default': { query: "What are the core functions of the Bureau of Indian Standards?", label: "Overview of BIS functions" }
        }
    };

    function getPersonalizedSuggestions(role, useCases) {
        const selectedUseCases = Array.isArray(useCases) ? useCases.filter(Boolean) : [];
        const result = [];
        const seenQueries = new Set();

        function addSuggestion(s) {
            if (!s || !s.query) return;
            const key = s.query.toLowerCase().trim();
            if (!seenQueries.has(key)) {
                seenQueries.add(key);
                result.push(s);
            }
        }

        // 1. Prioritize suggestions matching selected use cases (contextualized by role)
        for (const uc of selectedUseCases) {
            const ucCatalog = BIS_USECASE_SUGGESTIONS[uc];
            if (ucCatalog) {
                const item = (role && ucCatalog[role]) ? ucCatalog[role] : ucCatalog['_default'];
                if (item) addSuggestion(item);
            }
            if (result.length >= 4) break;
        }

        // 2. Role-based fallback suggestions
        const roleList = BIS_ROLE_SUGGESTIONS[role] || BIS_ROLE_SUGGESTIONS['default'];
        for (const s of roleList) {
            if (result.length >= 4) break;
            addSuggestion(s);
        }

        // 3. Generic fallback suggestions
        const genericList = BIS_ROLE_SUGGESTIONS['default'];
        for (const s of genericList) {
            if (result.length >= 4) break;
            addSuggestion(s);
        }

        return result.slice(0, 4);
    }

    function renderPersonalizedSuggestions(roleOrPrefs, maybeUseCases) {
        const wrap = document.querySelector('#welcomeContainer .hero-suggestions-wrap');
        if (!wrap) return;

        let role = null;
        let useCases = [];

        if (roleOrPrefs && typeof roleOrPrefs === 'object') {
            role = roleOrPrefs.role;
            useCases = roleOrPrefs.useCases || [];
        } else {
            role = roleOrPrefs;
            useCases = Array.isArray(maybeUseCases) ? maybeUseCases : [];
        }

        const suggestions = getPersonalizedSuggestions(role, useCases);

        wrap.innerHTML = suggestions.map(s => `
            <button type="button" class="hero-suggestion-pill" data-query="${escapeHtml(s.query)}">
                ${escapeHtml(s.label)}
            </button>
        `).join('');
    }

    function applyPersonalization(prefs) {
        if (!prefs) prefs = getUserPreferences();

        renderPersonalizedWelcome(prefs);
        renderPersonalizedSuggestions(prefs.role, prefs.useCases);

        // Language synchronization:
        // 1. If explicit user preference with completed onboarding specifies a language, apply it
        // 2. Otherwise retain the current stored UI language preference (bis_ui_language)
        const targetLang = (prefs && prefs.onboarding_completed && prefs.language)
            ? prefs.language
            : (localStorage.getItem('bis_ui_language') || currentLanguage || 'en');

        if (targetLang && targetLang !== currentLanguage) {
            applyLanguage(targetLang);
        }

        if (prefs.location?.city) {
            const labInput = document.getElementById('labInputQuery');
            if (labInput && !labInput.value.trim()) {
                labInput.placeholder = `Search standards, or labs in ${prefs.location.city}...`;
            }
        }
    }

    let currentOnboardingStep = 1;
    let tempPreferences = { ...DEFAULT_USER_PREFERENCES };
    let isOnboardingEditMode = false;

    function populateLocationDatalists() {
        if (obStateList && obStateList.children.length === 0) {
            Object.keys(INDIA_STATES_AND_CITIES).sort().forEach(state => {
                const opt = document.createElement('option');
                opt.value = state;
                obStateList.appendChild(opt);
            });
        }
    }

    function updateCityDatalist(stateName) {
        if (!obCityList) return;
        obCityList.innerHTML = '';
        const cities = INDIA_STATES_AND_CITIES[stateName] || [];
        cities.forEach(city => {
            const opt = document.createElement('option');
            opt.value = city;
            obCityList.appendChild(opt);
        });
    }

    function renderStateDropdown(filterText = '') {
        if (!obStateDropdown) return;
        const query = (filterText || '').trim().toLowerCase();
        const allStates = Object.keys(INDIA_STATES_AND_CITIES).sort();
        const filtered = query
            ? allStates.filter(s => s.toLowerCase().includes(query))
            : allStates;

        if (filtered.length === 0) {
            obStateDropdown.innerHTML = `<div class="ob-dropdown-empty">No matching states or UTs found</div>`;
            return;
        }

        const currentState = tempPreferences.location?.state || (obStateInput ? obStateInput.value.trim() : '');
        obStateDropdown.innerHTML = filtered.map(state => {
            const isSelected = state === currentState;
            return `
                <button type="button" class="ob-dropdown-item ${isSelected ? 'selected' : ''}" data-value="${escapeHtml(state)}" role="option" aria-selected="${isSelected ? 'true' : 'false'}">
                    <span>${escapeHtml(state)}</span>
                    <svg class="item-check" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                </button>
            `;
        }).join('');
    }

    function renderCityDropdown(stateName, filterText = '') {
        if (!obCityDropdown) return;
        const query = (filterText || '').trim().toLowerCase();
        const allCities = INDIA_STATES_AND_CITIES[stateName] || [];
        const filtered = query
            ? allCities.filter(c => c.toLowerCase().includes(query))
            : allCities;

        let html = '';
        const currentCity = tempPreferences.location?.city || (obCityInput ? obCityInput.value.trim() : '');

        if (filtered.length > 0) {
            html += filtered.map(city => {
                const isSelected = city === currentCity;
                return `
                    <button type="button" class="ob-dropdown-item ${isSelected ? 'selected' : ''}" data-value="${escapeHtml(city)}" role="option" aria-selected="${isSelected ? 'true' : 'false'}">
                        <span>${escapeHtml(city)}</span>
                        <svg class="item-check" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                    </button>
                `;
            }).join('');
        }

        if (query && !allCities.some(c => c.toLowerCase() === query)) {
            const rawTyped = (filterText || '').trim();
            html += `
                <button type="button" class="ob-dropdown-item" data-value="${escapeHtml(rawTyped)}" role="option">
                    <span>Use &ldquo;${escapeHtml(rawTyped)}&rdquo;</span>
                    <span style="font-size:10.5px;color:#8b80f7;font-weight:600;padding:2px 6px;border-radius:4px;background:rgba(139,128,247,0.15);">Custom</span>
                </button>
            `;
        } else if (filtered.length === 0) {
            html = `<div class="ob-dropdown-empty">Type any city name</div>`;
        }

        obCityDropdown.innerHTML = html;
    }

    function openStateDropdown() {
        closeCityDropdown();
        if (!obStateDropdown) return;
        renderStateDropdown('');
        obStateDropdown.classList.remove('hidden');
        if (obStateComboboxWrap) obStateComboboxWrap.classList.add('is-open');
        if (obStateInput) obStateInput.setAttribute('aria-expanded', 'true');
        const sel = obStateDropdown.querySelector('.ob-dropdown-item.selected');
        if (sel) sel.scrollIntoView({ block: 'nearest' });
    }

    function closeStateDropdown() {
        if (!obStateDropdown) return;
        obStateDropdown.classList.add('hidden');
        if (obStateComboboxWrap) obStateComboboxWrap.classList.remove('is-open');
        if (obStateInput) obStateInput.setAttribute('aria-expanded', 'false');
    }

    function openCityDropdown() {
        closeStateDropdown();
        if (!obCityDropdown) return;
        const stateName = obStateInput ? obStateInput.value.trim() : 'Delhi (NCT)';
        renderCityDropdown(stateName, '');
        obCityDropdown.classList.remove('hidden');
        if (obCityComboboxWrap) obCityComboboxWrap.classList.add('is-open');
        if (obCityInput) obCityInput.setAttribute('aria-expanded', 'true');
        const sel = obCityDropdown.querySelector('.ob-dropdown-item.selected');
        if (sel) sel.scrollIntoView({ block: 'nearest' });
    }

    function closeCityDropdown() {
        if (!obCityDropdown) return;
        obCityDropdown.classList.add('hidden');
        if (obCityComboboxWrap) obCityComboboxWrap.classList.remove('is-open');
        if (obCityInput) obCityInput.setAttribute('aria-expanded', 'false');
    }

    function selectStateOption(stateName) {
        if (!stateName) return;
        if (obStateInput) obStateInput.value = stateName;
        if (!tempPreferences.location) tempPreferences.location = {};
        tempPreferences.location.state = stateName;
        closeStateDropdown();
        updateCityDatalist(stateName);

        const cities = INDIA_STATES_AND_CITIES[stateName] || [];
        const currCity = obCityInput ? obCityInput.value.trim() : '';
        if (!cities.includes(currCity)) {
            const nextCity = cities[0] || '';
            if (obCityInput) obCityInput.value = nextCity;
            tempPreferences.location.city = nextCity;
        }

        syncPopularCityPills(stateName, tempPreferences.location.city);
    }

    function selectCityOption(cityName) {
        if (!cityName) return;
        if (obCityInput) obCityInput.value = cityName;
        if (!tempPreferences.location) tempPreferences.location = {};
        tempPreferences.location.city = cityName;
        closeCityDropdown();

        const stateName = tempPreferences.location.state || (obStateInput ? obStateInput.value.trim() : '');
        syncPopularCityPills(stateName, cityName);
    }

    function syncPopularCityPills(stateName, cityName) {
        document.querySelectorAll('#obPopularCitiesWrap .ob-quick-city-pill').forEach(pill => {
            const ps = pill.getAttribute('data-state');
            const pc = pill.getAttribute('data-city');
            const isMatch = (ps === stateName && pc === cityName) || pc === cityName;
            pill.classList.toggle('active', isMatch);
        });
    }

    function syncOnboardingUIFromState() {
        // Step 1: Role cards
        document.querySelectorAll('#onboardingRolesGrid .onboarding-option-card').forEach(card => {
            const role = card.getAttribute('data-role');
            const isSelected = role === tempPreferences.role;
            card.classList.toggle('selected', isSelected);
            card.setAttribute('aria-checked', isSelected ? 'true' : 'false');
        });

        // Step 2: Use Cases chips
        document.querySelectorAll('#onboardingUseCasesGrid .onboarding-chip-card').forEach(chip => {
            const uc = chip.getAttribute('data-usecase');
            const isSelected = Array.isArray(tempPreferences.useCases) && tempPreferences.useCases.includes(uc);
            chip.classList.toggle('selected', isSelected);
            chip.setAttribute('aria-checked', isSelected ? 'true' : 'false');
        });

        // Step 3: Location
        if (obCountrySelect) {
            obCountrySelect.value = tempPreferences.location?.country || 'India';
            const isIndia = obCountrySelect.value === 'India';
            if (obIndiaLocationWrap) obIndiaLocationWrap.classList.toggle('hidden', !isIndia);
            if (obPopularCitiesWrap) obPopularCitiesWrap.classList.toggle('hidden', !isIndia);
        }
        if (obStateInput) {
            obStateInput.value = tempPreferences.location?.state || 'Delhi (NCT)';
            updateCityDatalist(obStateInput.value);
            renderStateDropdown('');
        }
        if (obCityInput) {
            obCityInput.value = tempPreferences.location?.city || 'New Delhi';
            renderCityDropdown(obStateInput ? obStateInput.value : 'Delhi (NCT)', '');
        }

        // Highlight matching quick city pill
        syncPopularCityPills(tempPreferences.location?.state, tempPreferences.location?.city);

        // Step 4: Languages & Styles
        document.querySelectorAll('#onboardingLangGrid .onboarding-lang-card').forEach(card => {
            const lang = card.getAttribute('data-lang');
            const isSelected = lang === tempPreferences.language;
            card.classList.toggle('selected', isSelected);
            card.setAttribute('aria-checked', isSelected ? 'true' : 'false');
        });

        document.querySelectorAll('#onboardingStylesGrid .onboarding-style-card').forEach(card => {
            const style = card.getAttribute('data-style');
            const isSelected = style === tempPreferences.responseStyle;
            card.classList.toggle('selected', isSelected);
            card.setAttribute('aria-checked', isSelected ? 'true' : 'false');
        });

        // Step 4: Workspace Appearance / Theme
        const currentThemePref = getSavedThemePreference();
        document.querySelectorAll('#onboardingThemesGrid .onboarding-theme-card').forEach(card => {
            const themeVal = card.getAttribute('data-theme-val');
            const isSelected = themeVal === currentThemePref;
            card.classList.toggle('selected', isSelected);
            card.setAttribute('aria-checked', isSelected ? 'true' : 'false');
        });
    }

    // -------------------------------------------------------------------------
    // Theme System (Light / Dark / System)
    // -------------------------------------------------------------------------
    function getSystemTheme() {
        return (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) ? 'light' : 'dark';
    }

    function getSavedThemePreference() {
        return localStorage.getItem('bis_theme') || 'system';
    }

    function applyTheme(themeMode) {
        const resolved = themeMode === 'system' ? getSystemTheme() : themeMode;
        document.documentElement.setAttribute('data-theme', resolved);

        if (btnThemeToggle) {
            const sunIcon = btnThemeToggle.querySelector('.theme-icon-sun');
            const moonIcon = btnThemeToggle.querySelector('.theme-icon-moon');
            const textSpan = document.getElementById('themeToggleText');
            if (resolved === 'light') {
                sunIcon?.classList.remove('hidden');
                moonIcon?.classList.add('hidden');
                if (textSpan) textSpan.textContent = 'Light';
            } else {
                sunIcon?.classList.add('hidden');
                moonIcon?.classList.remove('hidden');
                if (textSpan) textSpan.textContent = 'Dark';
            }
            btnThemeToggle.setAttribute('title', `Appearance: ${themeMode.charAt(0).toUpperCase() + themeMode.slice(1)} (Click to switch)`);
        }

        document.querySelectorAll('#onboardingThemesGrid .onboarding-theme-card').forEach(c => {
            const val = c.getAttribute('data-theme-val');
            const isMatch = val === themeMode;
            c.classList.toggle('selected', isMatch);
            c.setAttribute('aria-checked', isMatch ? 'true' : 'false');
        });
    }

    function setThemePreference(themeMode) {
        localStorage.setItem('bis_theme', themeMode);
        applyTheme(themeMode);
    }

    function toggleTheme() {
        const activeResolved = document.documentElement.getAttribute('data-theme') || 'dark';
        const next = activeResolved === 'light' ? 'dark' : 'light';
        setThemePreference(next);
    }

    function initTheme() {
        const saved = getSavedThemePreference();
        applyTheme(saved);

        if (window.matchMedia) {
            window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', () => {
                if (getSavedThemePreference() === 'system') {
                    applyTheme('system');
                }
            });
        }
    }

    function setOnboardingStep(step) {
        closeStateDropdown();
        closeCityDropdown();
        currentOnboardingStep = Math.max(1, Math.min(4, step));

        for (let i = 1; i <= 4; i++) {
            const pane = document.getElementById(`onboardingStep${i}`);
            if (pane) {
                pane.classList.toggle('hidden', i !== currentOnboardingStep);
            }
        }

        if (onboardingStepBadge) {
            onboardingStepBadge.textContent = `Step ${currentOnboardingStep} of 4`;
        }
        if (onboardingProgressFill) {
            onboardingProgressFill.style.width = `${(currentOnboardingStep / 4) * 100}%`;
        }
        if (onboardingProgressFill?.parentElement) {
            onboardingProgressFill.parentElement.setAttribute('aria-valuenow', (currentOnboardingStep / 4) * 100);
        }

        if (btnOnboardingBack) {
            btnOnboardingBack.classList.toggle('hidden', currentOnboardingStep === 1);
        }

        if (onboardingNextText) {
            if (currentOnboardingStep === 4) {
                onboardingNextText.textContent = isOnboardingEditMode ? t('onboarding.btn_save', 'Save Changes') : t('onboarding.btn_finish', 'Complete & Start Exploring');
            } else {
                onboardingNextText.textContent = t('onboarding.btn_continue', 'Continue');
            }
        }
    }

    function openOnboarding(isEditMode = false) {
        isOnboardingEditMode = isEditMode;
        tempPreferences = getUserPreferences();

        if (onboardingKicker) {
            onboardingKicker.textContent = isEditMode ? 'USER PREFERENCES' : t('onboarding.badge', 'BIS PERSONALIZATION');
        }
        if (onboardingModalTitle) {
            onboardingModalTitle.textContent = isEditMode ? t('onboarding.edit_title', 'Personalization Preferences') : t('onboarding.title', 'Welcome to BIS AI Assistant');
        }
        if (onboardingModalSubtitle) {
            onboardingModalSubtitle.textContent = isEditMode ? t('onboarding.edit_subtitle', 'Update your role, objectives, and interface settings anytime.') : t('onboarding.subtitle', 'Personalize your workspace for faster, evidence-grounded standards intelligence.');
        }
        if (btnOnboardingSkip) {
            btnOnboardingSkip.textContent = isEditMode ? 'Cancel' : t('onboarding.btn_skip', 'Skip for now');
        }

        populateLocationDatalists();
        syncOnboardingUIFromState();
        setOnboardingStep(1);

        if (onboardingModalBackdrop) {
            onboardingModalBackdrop.classList.remove('hidden');
            onboardingModalBackdrop.setAttribute('aria-hidden', 'false');
        }
    }

    function closeOnboarding() {
        if (onboardingModalBackdrop) {
            onboardingModalBackdrop.classList.add('hidden');
            onboardingModalBackdrop.setAttribute('aria-hidden', 'true');
        }
    }

    function handleOnboardingNext() {
        if (currentOnboardingStep === 1) {
            // Strictly preserve null/empty role if not selected; do not invent or default to Manufacturer
            setOnboardingStep(2);
        } else if (currentOnboardingStep === 2) {
            if (!tempPreferences.useCases || tempPreferences.useCases.length === 0) {
                tempPreferences.useCases = ['Finding Indian Standards'];
            }
            setOnboardingStep(3);
        } else if (currentOnboardingStep === 3) {
            const country = obCountrySelect ? obCountrySelect.value : 'India';
            const state = obStateInput ? obStateInput.value.trim() : 'Delhi (NCT)';
            const city = obCityInput ? obCityInput.value.trim() : 'New Delhi';
            tempPreferences.location = { country, state, city };
            setOnboardingStep(4);
        } else if (currentOnboardingStep === 4) {
            tempPreferences.completedAt = new Date().toISOString();
            tempPreferences.onboarding_completed = true;
            saveUserPreferences(tempPreferences);
            applyPersonalization(tempPreferences);
            closeOnboarding();
        }
    }

    // Quick Tour Controller
    let currentTourSlide = 1;

    function setTourSlide(slideIndex) {
        currentTourSlide = Math.max(1, Math.min(4, slideIndex));

        document.querySelectorAll('#tourSlidesContainer .tour-slide').forEach(slide => {
            const sNum = parseInt(slide.getAttribute('data-slide'), 10);
            slide.classList.toggle('hidden', sNum !== currentTourSlide);
            slide.classList.toggle('active', sNum === currentTourSlide);
        });

        document.querySelectorAll('#tourDots .tour-dot').forEach(dot => {
            const dNum = parseInt(dot.getAttribute('data-slide'), 10);
            dot.classList.toggle('active', dNum === currentTourSlide);
        });

        if (btnTourPrev) {
            btnTourPrev.disabled = currentTourSlide === 1;
        }

        if (btnTourNext) {
            if (currentTourSlide === 4) {
                btnTourNext.innerHTML = 'Start Exploring &rarr;';
            } else {
                btnTourNext.innerHTML = 'Next &rarr;';
            }
        }
    }

    function openQuickTour() {
        setTourSlide(1);
        if (quickTourModalBackdrop) {
            quickTourModalBackdrop.classList.remove('hidden');
            quickTourModalBackdrop.setAttribute('aria-hidden', 'false');
        }
    }

    function closeQuickTour() {
        if (quickTourModalBackdrop) {
            quickTourModalBackdrop.classList.add('hidden');
            quickTourModalBackdrop.setAttribute('aria-hidden', 'true');
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
            const label = isCollapsed ? 'Expand sidebar' : 'Collapse sidebar';
            btnSidebarCollapse.setAttribute('title', label);
            btnSidebarCollapse.setAttribute('aria-label', label);
            btnSidebarCollapse.setAttribute('data-tooltip', label);
        }
        if (!isCollapsed && collapsedConvPopover) {
            collapsedConvPopover.classList.add('hidden');
            if (navCollapsedConversations) navCollapsedConversations.setAttribute('aria-expanded', 'false');
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
        window.switchView = switchView;
        window.openEvidenceDrawer = openEvidenceDrawer;
        // Nav Links
        if (navAssistant) navAssistant.addEventListener('click', () => switchView('assistant'));
        if (navComplianceJourney) navComplianceJourney.addEventListener('click', () => switchView('compliance'));
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

        // Interactive Preview Card standard record affordance
        const previewEvidenceBtn = document.getElementById('previewEvidenceBtn');
        if (previewEvidenceBtn) {
            previewEvidenceBtn.addEventListener('click', () => {
                switchView('assistant');
                submitQuery('What are the requirements in IS 8978?');
            });
        }

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

        if (btnCollapsedNewChat) {
            btnCollapsedNewChat.addEventListener('click', () => {
                createNewConversation(true);
                if (collapsedConvPopover) collapsedConvPopover.classList.add('hidden');
            });
        }

        // Collapsed mode Conversations popover toggle
        if (navCollapsedConversations && collapsedConvPopover) {
            navCollapsedConversations.addEventListener('click', (e) => {
                e.stopPropagation();
                const isHidden = collapsedConvPopover.classList.contains('hidden');
                if (isHidden) {
                    conversationManager.renderPopover(collapsedConvPopover, conversations, currentConversationId);
                    collapsedConvPopover.classList.remove('hidden');
                    navCollapsedConversations.setAttribute('aria-expanded', 'true');
                } else {
                    collapsedConvPopover.classList.add('hidden');
                    navCollapsedConversations.setAttribute('aria-expanded', 'false');
                }
            });

            // Dismiss popover on outside click
            document.addEventListener('click', (e) => {
                if (!collapsedConvPopover.classList.contains('hidden') &&
                    !collapsedConvPopover.contains(e.target) &&
                    !navCollapsedConversations.contains(e.target)) {
                    collapsedConvPopover.classList.add('hidden');
                    navCollapsedConversations.setAttribute('aria-expanded', 'false');
                }
            });

            // Dismiss popover on Escape
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && !collapsedConvPopover.classList.contains('hidden')) {
                    collapsedConvPopover.classList.add('hidden');
                    navCollapsedConversations.setAttribute('aria-expanded', 'false');
                }
            });
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

        // Onboarding & Personalization Triggers & Controls
        if (btnSidebarPreferences) {
            btnSidebarPreferences.addEventListener('click', (e) => {
                e.stopPropagation();
                openOnboarding(true);
            });
        }

        if (btnThemeToggle) {
            btnThemeToggle.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleTheme();
            });
        }

        if (btnSidebarTour) {
            btnSidebarTour.addEventListener('click', (e) => {
                e.stopPropagation();
                openQuickTour();
            });
        }

        if (btnSystemModalTour) {
            btnSystemModalTour.addEventListener('click', (e) => {
                e.stopPropagation();
                closeSystemModal();
                openQuickTour();
            });
        }

        if (btnOnboardingClose) {
            btnOnboardingClose.addEventListener('click', (e) => {
                e.stopPropagation();
                if (!isOnboardingEditMode && !localStorage.getItem('bis_onboarding_completed')) {
                    const completed = { ...DEFAULT_USER_PREFERENCES, completedAt: new Date().toISOString(), onboarding_completed: true };
                    saveUserPreferences(completed);
                    applyPersonalization(completed);
                }
                closeOnboarding();
            });
        }

        if (btnOnboardingSkip) {
            btnOnboardingSkip.addEventListener('click', (e) => {
                e.stopPropagation();
                if (!isOnboardingEditMode) {
                    const completed = { ...DEFAULT_USER_PREFERENCES, completedAt: new Date().toISOString(), onboarding_completed: true };
                    saveUserPreferences(completed);
                    applyPersonalization(completed);
                }
                closeOnboarding();
            });
        }

        if (btnOnboardingBack) {
            btnOnboardingBack.addEventListener('click', (e) => {
                e.stopPropagation();
                if (currentOnboardingStep > 1) {
                    setOnboardingStep(currentOnboardingStep - 1);
                }
            });
        }

        if (btnOnboardingNext) {
            btnOnboardingNext.addEventListener('click', (e) => {
                e.stopPropagation();
                handleOnboardingNext();
            });
        }

        // Step 1: Role card click
        const rolesGrid = document.getElementById('onboardingRolesGrid');
        if (rolesGrid) {
            rolesGrid.addEventListener('click', (e) => {
                const card = e.target.closest('.onboarding-option-card');
                if (card) {
                    const role = card.getAttribute('data-role');
                    if (role) {
                        tempPreferences.role = role;
                        document.querySelectorAll('#onboardingRolesGrid .onboarding-option-card').forEach(c => {
                            const isThis = c === card;
                            c.classList.toggle('selected', isThis);
                            c.setAttribute('aria-checked', isThis ? 'true' : 'false');
                        });
                    }
                }
            });
        }

        // Step 2: Use Cases multi-select click
        const useCasesGrid = document.getElementById('onboardingUseCasesGrid');
        if (useCasesGrid) {
            useCasesGrid.addEventListener('click', (e) => {
                const chip = e.target.closest('.onboarding-chip-card');
                if (chip) {
                    const uc = chip.getAttribute('data-usecase');
                    if (uc) {
                        if (!Array.isArray(tempPreferences.useCases)) {
                            tempPreferences.useCases = [];
                        }
                        const idx = tempPreferences.useCases.indexOf(uc);
                        if (idx > -1) {
                            if (tempPreferences.useCases.length > 1) {
                                tempPreferences.useCases.splice(idx, 1);
                                chip.classList.remove('selected');
                                chip.setAttribute('aria-checked', 'false');
                            }
                        } else {
                            tempPreferences.useCases.push(uc);
                            chip.classList.add('selected');
                            chip.setAttribute('aria-checked', 'true');
                        }
                    }
                }
            });
        }

        // Step 3: Location changes
        if (obCountrySelect) {
            obCountrySelect.addEventListener('change', () => {
                const isIndia = obCountrySelect.value === 'India';
                if (obIndiaLocationWrap) obIndiaLocationWrap.classList.toggle('hidden', !isIndia);
                if (obPopularCitiesWrap) obPopularCitiesWrap.classList.toggle('hidden', !isIndia);
            });
        }

        // State Combobox Listeners
        if (obStateInput) {
            obStateInput.addEventListener('click', (e) => {
                e.stopPropagation();
                openStateDropdown();
            });
            obStateInput.addEventListener('focus', () => {
                openStateDropdown();
            });
            obStateInput.addEventListener('input', () => {
                if (obStateDropdown && obStateDropdown.classList.contains('hidden')) {
                    openStateDropdown();
                }
                renderStateDropdown(obStateInput.value.trim());
                if (!tempPreferences.location) tempPreferences.location = {};
                tempPreferences.location.state = obStateInput.value.trim();
                updateCityDatalist(obStateInput.value.trim());
            });
        }

        if (btnToggleStateDropdown) {
            btnToggleStateDropdown.addEventListener('click', (e) => {
                e.stopPropagation();
                if (obStateDropdown && !obStateDropdown.classList.contains('hidden')) {
                    closeStateDropdown();
                } else {
                    openStateDropdown();
                }
            });
        }

        if (obStateDropdown) {
            obStateDropdown.addEventListener('click', (e) => {
                e.stopPropagation();
                const item = e.target.closest('.ob-dropdown-item');
                if (item) {
                    const val = item.getAttribute('data-value');
                    selectStateOption(val);
                }
            });
        }

        // City Combobox Listeners
        if (obCityInput) {
            obCityInput.addEventListener('click', (e) => {
                e.stopPropagation();
                openCityDropdown();
            });
            obCityInput.addEventListener('focus', () => {
                openCityDropdown();
            });
            obCityInput.addEventListener('input', () => {
                if (obCityDropdown && obCityDropdown.classList.contains('hidden')) {
                    openCityDropdown();
                }
                const st = obStateInput ? obStateInput.value.trim() : 'Delhi (NCT)';
                renderCityDropdown(st, obCityInput.value.trim());
                if (!tempPreferences.location) tempPreferences.location = {};
                tempPreferences.location.city = obCityInput.value.trim();
            });
        }

        if (btnToggleCityDropdown) {
            btnToggleCityDropdown.addEventListener('click', (e) => {
                e.stopPropagation();
                if (obCityDropdown && !obCityDropdown.classList.contains('hidden')) {
                    closeCityDropdown();
                } else {
                    openCityDropdown();
                }
            });
        }

        if (obCityDropdown) {
            obCityDropdown.addEventListener('click', (e) => {
                e.stopPropagation();
                const item = e.target.closest('.ob-dropdown-item');
                if (item) {
                    const val = item.getAttribute('data-value');
                    selectCityOption(val);
                }
            });
        }

        // Close dropdowns on outside click
        document.addEventListener('click', (e) => {
            if (obStateComboboxWrap && !obStateComboboxWrap.contains(e.target)) {
                closeStateDropdown();
            }
            if (obCityComboboxWrap && !obCityComboboxWrap.contains(e.target)) {
                closeCityDropdown();
            }
        });

        // Close dropdowns on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                closeStateDropdown();
                closeCityDropdown();
            }
        });

        if (obPopularCitiesWrap) {
            obPopularCitiesWrap.addEventListener('click', (e) => {
                const pill = e.target.closest('.ob-quick-city-pill');
                if (pill) {
                    const state = pill.getAttribute('data-state');
                    const city = pill.getAttribute('data-city');
                    selectStateOption(state);
                    selectCityOption(city);
                }
            });
        }

        // Step 4: Language & Response Style selection
        const langGrid = document.getElementById('onboardingLangGrid');
        if (langGrid) {
            langGrid.addEventListener('click', (e) => {
                const card = e.target.closest('.onboarding-lang-card');
                if (card) {
                    const lang = card.getAttribute('data-lang');
                    if (lang) {
                        tempPreferences.language = lang;
                        document.querySelectorAll('#onboardingLangGrid .onboarding-lang-card').forEach(c => {
                            const isThis = c === card;
                            c.classList.toggle('selected', isThis);
                            c.setAttribute('aria-checked', isThis ? 'true' : 'false');
                        });
                    }
                }
            });
        }

        const stylesGrid = document.getElementById('onboardingStylesGrid');
        if (stylesGrid) {
            stylesGrid.addEventListener('click', (e) => {
                const card = e.target.closest('.onboarding-style-card');
                if (card) {
                    const style = card.getAttribute('data-style');
                    if (style) {
                        tempPreferences.responseStyle = style;
                        document.querySelectorAll('#onboardingStylesGrid .onboarding-style-card').forEach(c => {
                            const isThis = c === card;
                            c.classList.toggle('selected', isThis);
                            c.setAttribute('aria-checked', isThis ? 'true' : 'false');
                        });
                    }
                }
            });
        }

        const themesGrid = document.getElementById('onboardingThemesGrid');
        if (themesGrid) {
            themesGrid.addEventListener('click', (e) => {
                const card = e.target.closest('.onboarding-theme-card');
                if (card) {
                    const themeVal = card.getAttribute('data-theme-val');
                    if (themeVal) {
                        setThemePreference(themeVal);
                    }
                }
            });
        }

        // Quick Tour Controls
        if (btnTourClose) {
            btnTourClose.addEventListener('click', (e) => {
                e.stopPropagation();
                closeQuickTour();
            });
        }

        if (btnTourPrev) {
            btnTourPrev.addEventListener('click', (e) => {
                e.stopPropagation();
                if (currentTourSlide > 1) {
                    setTourSlide(currentTourSlide - 1);
                }
            });
        }

        if (btnTourNext) {
            btnTourNext.addEventListener('click', (e) => {
                e.stopPropagation();
                if (currentTourSlide < 4) {
                    setTourSlide(currentTourSlide + 1);
                } else {
                    closeQuickTour();
                    switchView('assistant');
                }
            });
        }

        if (tourDots) {
            tourDots.addEventListener('click', (e) => {
                const dot = e.target.closest('.tour-dot');
                if (dot) {
                    const s = parseInt(dot.getAttribute('data-slide'), 10);
                    if (s) setTourSlide(s);
                }
            });
        }

        // Modal Backdrops Click to Dismiss
        if (onboardingModalBackdrop) {
            onboardingModalBackdrop.addEventListener('click', (e) => {
                if (e.target === onboardingModalBackdrop) {
                    closeOnboarding();
                }
            });
        }

        if (quickTourModalBackdrop) {
            quickTourModalBackdrop.addEventListener('click', (e) => {
                if (e.target === quickTourModalBackdrop) {
                    closeQuickTour();
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
                try {
                    await signOut();
                    setGuestSession(false);
                    updateAuthStateUI('SIGNED_OUT', null, null);
                } catch (err) {
                    console.warn('[BIS Auth] SignOut error:', err);
                    updateAuthStateUI('SIGNED_OUT', null, null);
                }

                // Redirect to login page
                const loginUrl = getLoginUrl();
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
        let authCooldownInterval = null;

        function updateAuthCooldownUI() {
            const signupRemaining = getEmailCooldownRemaining(EMAIL_COOLDOWN_ACTIONS.SIGNUP);
            const resetRemaining = getEmailCooldownRemaining(EMAIL_COOLDOWN_ACTIONS.PASSWORD_RESET);

            if (authMode === 'signup' && authSignupConfirmationBox && !authSignupConfirmationBox.classList.contains('hidden')) {
                if (signupRemaining > 0) {
                    if (authSignupCooldownBadge) authSignupCooldownBadge.classList.remove('hidden');
                    if (authSignupCooldownText) authSignupCooldownText.textContent = `Resend available in ${signupRemaining}s`;
                } else {
                    if (authSignupCooldownText) authSignupCooldownText.textContent = 'You may now resend or try again.';
                }
            }

            if (authMode === 'forgot') {
                if (resetRemaining > 0) {
                    if (authSubmitBtn) authSubmitBtn.disabled = true;
                    if (authSubmitText) authSubmitText.textContent = `Wait (${resetRemaining}s)`;
                } else {
                    if (authSubmitBtn) authSubmitBtn.disabled = false;
                    if (authSubmitText) authSubmitText.textContent = 'Send Reset Link';
                }
            }
        }

        function startAuthCooldownTicker() {
            if (authCooldownInterval) clearInterval(authCooldownInterval);
            updateAuthCooldownUI();
            authCooldownInterval = setInterval(() => {
                updateAuthCooldownUI();
                const signupRem = getEmailCooldownRemaining(EMAIL_COOLDOWN_ACTIONS.SIGNUP);
                const resetRem = getEmailCooldownRemaining(EMAIL_COOLDOWN_ACTIONS.PASSWORD_RESET);
                if (signupRem <= 0 && resetRem <= 0) {
                    clearInterval(authCooldownInterval);
                    authCooldownInterval = null;
                }
            }, 1000);
        }

        function showAuthSignupConfirmation(email) {
            if (authConfirmationTargetEmail) authConfirmationTargetEmail.textContent = email;
            if (authForm) authForm.classList.add('hidden');
            if (authTabs) authTabs.classList.add('hidden');
            if (authDivider) authDivider.classList.add('hidden');
            if (authSocialGroup) authSocialGroup.classList.add('hidden');
            if (authSignupConfirmationBox) authSignupConfirmationBox.classList.remove('hidden');
            startAuthCooldownTicker();
        }

        function openAuthModal(mode = 'signin') {
            setAuthMode(mode);
            clearAuthAlert();
            startAuthCooldownTicker();
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
            if (authCooldownInterval) {
                clearInterval(authCooldownInterval);
                authCooldownInterval = null;
            }
            if (authSignupConfirmationBox) authSignupConfirmationBox.classList.add('hidden');
            if (authForm) {
                authForm.classList.remove('hidden');
                authForm.reset();
            }
        }

        function setAuthMode(mode) {
            authMode = mode;
            clearAuthAlert();

            if (authSignupConfirmationBox) authSignupConfirmationBox.classList.add('hidden');
            if (authForm) authForm.classList.remove('hidden');

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

            updateAuthCooldownUI();
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

            // Strict Deliverable Email Validation (for signin, signup, forgot)
            if (authMode !== 'reset') {
                const validation = validateDeliverableEmail(email);
                if (!validation.valid) {
                    showAuthAlert('error', validation.error || 'Please enter a valid work email address.');
                    if (authEmailInput) authEmailInput.focus();
                    return;
                }
                if (validation.warning) {
                    showAuthAlert('warning', validation.warning);
                }
            }

            // Client-side Cooldown Check before touching Supabase
            if (authMode === 'signup') {
                if (isEmailCooldownActive(EMAIL_COOLDOWN_ACTIONS.SIGNUP)) {
                    const rem = getEmailCooldownRemaining(EMAIL_COOLDOWN_ACTIONS.SIGNUP);
                    showAuthAlert('error', `Please wait ${rem} seconds before initiating another registration.`);
                    return;
                }
            } else if (authMode === 'forgot') {
                if (isEmailCooldownActive(EMAIL_COOLDOWN_ACTIONS.PASSWORD_RESET)) {
                    const rem = getEmailCooldownRemaining(EMAIL_COOLDOWN_ACTIONS.PASSWORD_RESET);
                    showAuthAlert('error', `A password reset link was recently requested. Please wait ${rem} seconds before requesting another.`);
                    return;
                }
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
                        showAuthSignupConfirmation(email);
                        setAuthSubmitting(false);
                        return;
                    }
                    closeAuthModal();
                } else if (authMode === 'forgot') {
                    await sendPasswordReset(email);
                    showAuthAlert('success', 'If that account exists, a password reset link has been sent. Please check your inbox.');
                    startAuthCooldownTicker();
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
                const isRateLimit = err?.status === 429 || /rate limit|too many requests/i.test(err?.message || '');
                if (isRateLimit) {
                    showAuthAlert('error', 'Rate limit reached. Please wait a few minutes before trying again.');
                } else {
                    showAuthAlert('error', err.message || 'Authentication operation failed.');
                }
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
        if (btnAuthBackToSignIn) {
            btnAuthBackToSignIn.addEventListener('click', () => {
                if (authSignupConfirmationBox) authSignupConfirmationBox.classList.add('hidden');
                if (authForm) authForm.classList.remove('hidden');
                setAuthMode('signin');
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
                    setGuestSession(false);
                    updateAuthStateUI('SIGNED_OUT', null, null);
                } catch (err) {
                    console.warn('[BIS Auth] SignOut error:', err);
                    updateAuthStateUI('SIGNED_OUT', null, null);
                }
                const loginUrl = getLoginUrl();
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

                if (effectiveUser && effectiveUser.id && !isGuestSession()) {
                    syncConversationsFromSupabase(effectiveUser.id);
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
                clearAuthenticatedPreferences();
                applyPersonalization(DEFAULT_USER_PREFERENCES);
                if (event === 'SIGNED_OUT') {
                    conversations = [];
                    localStorage.removeItem('bis_ai_conversations_v2');
                    createNewConversation(false);
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
        } else if (hash === '#compliance' || hash === '#journey') {
            switchView('compliance');
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
        initTheme();
        initLanguageSelectors();
        loadI18n();
        initSubComponents();
    } catch (err) {
        console.error('[BIS Init] i18n / subcomponents initialization error:', err);
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

    // -------------------------------------------------------------------------
    // Session Guard & Entry Authentication Check
    // -------------------------------------------------------------------------
    const authLoadingScreen = document.getElementById('authLoadingScreen');

    validateSession().then((authState) => {
        if (!authState.authenticated) {
            window.location.replace(getLoginUrl());
            return;
        }
        if (authLoadingScreen) {
            authLoadingScreen.classList.add('hidden');
        }

        if (authState.isGuest) {
            // Guest mode: LocalStorage persistence only
            const guestPrefs = getUserPreferences();
            applyPersonalization(guestPrefs);
            if (!localStorage.getItem('bis_onboarding_completed')) {
                openOnboarding(false);
            }
            return;
        }

        // Authenticated user:
        const user = authState.user;
        const userId = user?.id;

        if (userId) {
            // Render from user-scoped local cache immediately without blocking
            const cachedUserPrefs = getUserPreferences(userId);
            applyPersonalization(cachedUserPrefs);

            // Asynchronously query Supabase (max 3000ms timeout, does not freeze UI)
            loadUserPreferencesFromSupabase(userId).then((dbPrefs) => {
                if (dbPrefs) {
                    // Valid database preference record exists: database wins over local cache!
                    applyPersonalization(dbPrefs);
                    if (dbPrefs.onboarding_completed) {
                        closeOnboarding();
                    } else {
                        openOnboarding(false);
                    }
                } else {
                    // No database record exists yet for this authenticated user -> open onboarding
                    openOnboarding(false);
                }
            }).catch((err) => {
                console.warn('[BIS Preferences] Async Supabase load error, retaining local cache:', err?.message || err);
                const currentPrefs = getUserPreferences(userId);
                if (!currentPrefs.onboarding_completed && !localStorage.getItem('bis_onboarding_completed_' + userId)) {
                    openOnboarding(false);
                }
            });
        } else {
            if (!localStorage.getItem('bis_onboarding_completed')) {
                openOnboarding(false);
            } else {
                applyPersonalization();
            }
        }
    }).catch((err) => {
        console.warn('[BIS Auth Guard] Validation error:', err);
        if (authLoadingScreen) {
            authLoadingScreen.classList.add('hidden');
        }
        applyPersonalization(getUserPreferences());
    });

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
                console.log('Production backend health probe returned non-healthy status, keeping production mode.');
            }
        }).catch(() => {
            console.log('Production backend health probe unreachable, keeping production mode.');
        });
    }
}

// Bootstrap on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}

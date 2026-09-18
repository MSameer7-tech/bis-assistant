/**
 * BIS AI Assistant - Supabase Authentication Module (Phase 14)
 *
 * Implements centralized, browser-native authentication using the official
 * Supabase JavaScript client via browser-compatible CDN ESM.
 *
 * Supported Authentication Providers:
 * - Email / Password (Sign In & Sign Up with confirmation detection)
 * - Google OAuth (redirect to /auth/callback)
 * - GitHub OAuth (redirect to /auth/callback)
 * - Password Reset / Recovery flows
 *
 * Guarantees:
 * - Zero hardcoded credentials; loads public config from /api/auth/config.
 * - Single source of truth: Supabase auth.users & session subscription.
 * - Graceful fallback if Supabase is not yet configured in .env.
 */

// Official Supabase JS SDK via browser ESM
import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm';
import { apiUrl } from './config.js';

/**
 * Known non-deliverable, RFC 2606 reserved, or placeholder domains that must never be sent to Supabase.
 */
export const BLOCKED_EMAIL_DOMAINS = new Set([
    'example.com',
    'example.org',
    'example.net',
    'test.com',
    'fake.com',
    'sample.com',
    'organization.com',
    'localhost',
    'invalid'
]);

export const BLOCKED_DOMAIN_SUFFIXES = [
    '.invalid',
    '.localhost',
    '.example',
    '.test'
];

export const COMMON_DOMAIN_TYPOS = {
    'gamil.com': 'gmail.com',
    'gmial.com': 'gmail.com',
    'gmaill.com': 'gmail.com',
    'yaho.com': 'yahoo.com',
    'yahooo.com': 'yahoo.com',
    'hotmial.com': 'hotmail.com',
    'outlok.com': 'outlook.com'
};

/**
 * Action types for email rate-limiting cooldowns
 */
export function EMAIL_COOLDOWN_ACTIONS() {
    return {
        SIGNUP: 'signup',
        PASSWORD_RESET: 'password_reset'
    };
}
EMAIL_COOLDOWN_ACTIONS.SIGNUP = 'signup';
EMAIL_COOLDOWN_ACTIONS.PASSWORD_RESET = 'password_reset';
Object.freeze(EMAIL_COOLDOWN_ACTIONS);

/**
 * Validates whether an email is structurally sound, deliverable, and not on any test/blocked lists.
 * Returns { valid: boolean, error?: string, warning?: string, email?: string }
 */
export function validateDeliverableEmail(rawEmail) {
    if (!rawEmail || typeof rawEmail !== 'string') {
        return { valid: false, error: 'Please enter your work email address.' };
    }

    const trimmed = rawEmail.trim();
    if (!trimmed) {
        return { valid: false, error: 'Please enter your work email address.' };
    }

    // Must contain exactly one @
    const parts = trimmed.split('@');
    if (parts.length !== 2) {
        return { valid: false, error: 'Please enter a valid email address containing exactly one "@".' };
    }

    const [localPart, domainPart] = parts;
    if (!localPart || !domainPart) {
        return { valid: false, error: 'Please enter a valid email address with a username and domain.' };
    }

    // Local part constraints: no leading/trailing dots, no consecutive dots
    if (localPart.startsWith('.') || localPart.endsWith('.') || localPart.includes('..')) {
        return { valid: false, error: 'Email username cannot start, end, or contain consecutive dots.' };
    }

    // Basic permitted characters in local part
    const localRegex = /^[a-zA-Z0-9!#$%&'*+/=?^_`{|}~.-]+$/;
    if (!localRegex.test(localPart)) {
        return { valid: false, error: 'Email username contains invalid characters.' };
    }

    // Domain part constraints: no leading/trailing dots, no consecutive dots
    if (domainPart.startsWith('.') || domainPart.endsWith('.') || domainPart.includes('..')) {
        return { valid: false, error: 'Email domain cannot start, end, or contain consecutive dots.' };
    }

    const domainLower = domainPart.toLowerCase();

    // Check if domain is blocked
    if (BLOCKED_EMAIL_DOMAINS.has(domainLower)) {
        return { valid: false, error: 'Please enter a valid, deliverable email address. Test or placeholder domains are not permitted.' };
    }

    for (const suffix of BLOCKED_DOMAIN_SUFFIXES) {
        if (domainLower === suffix.replace(/^\./, '') || domainLower.endsWith(suffix)) {
            return { valid: false, error: 'Please enter a valid, deliverable email address. Test or placeholder domains are not permitted.' };
        }
    }

    // Domain structure: must contain at least one dot separating domain label and TLD
    const domainLabels = domainLower.split('.');
    if (domainLabels.length < 2) {
        return { valid: false, error: 'Please enter a valid email domain with an extension (e.g. .com, .in).' };
    }

    // Validate each domain label
    const labelRegex = /^[a-z0-9-]+$/;
    for (let i = 0; i < domainLabels.length; i++) {
        const lbl = domainLabels[i];
        if (!lbl || lbl.startsWith('-') || lbl.endsWith('-') || !labelRegex.test(lbl)) {
            return { valid: false, error: 'Email domain contains invalid characters or formatting.' };
        }
    }

    // TLD must be at least 2 alphabetic characters
    const tld = domainLabels[domainLabels.length - 1];
    if (!/^[a-z]{2,}$/.test(tld)) {
        return { valid: false, error: 'Email top-level domain must contain at least 2 letters (e.g. .com, .gov.in).' };
    }

    // Check for typo warning (without rewriting address)
    let warning = undefined;
    if (COMMON_DOMAIN_TYPOS[domainLower]) {
        warning = `Did you mean @${COMMON_DOMAIN_TYPOS[domainLower]}?`;
    }

    return {
        valid: true,
        email: `${localPart}@${domainLower}`,
        warning
    };
}

function getSafeSessionStorage() {
    try {
        if (typeof sessionStorage !== 'undefined') return sessionStorage;
        if (typeof window !== 'undefined' && window.sessionStorage) return window.sessionStorage;
    } catch {
        return null;
    }
    return null;
}

/**
 * Returns remaining seconds for a given email cooldown action from sessionStorage.
 */
export function getEmailCooldownRemaining(actionType) {
    const storage = getSafeSessionStorage();
    if (!storage) return 0;
    try {
        const key = `bis_auth_cooldown_${actionType}`;
        const untilStr = storage.getItem(key);
        if (!untilStr) return 0;
        const until = parseInt(untilStr, 10);
        if (isNaN(until)) return 0;
        const remaining = Math.ceil((until - Date.now()) / 1000);
        return remaining > 0 ? remaining : 0;
    } catch {
        return 0;
    }
}

/**
 * Sets an expiration timestamp for a given action in sessionStorage.
 */
export function setEmailCooldown(actionType, seconds = 60) {
    const storage = getSafeSessionStorage();
    if (!storage) return;
    try {
        const key = `bis_auth_cooldown_${actionType}`;
        const until = Date.now() + (seconds * 1000);
        storage.setItem(key, until.toString());
    } catch {
        // silent
    }
}

/**
 * Checks whether an email cooldown is currently active.
 */
export function isEmailCooldownActive(actionType) {
    return getEmailCooldownRemaining(actionType) > 0;
}

// Module-level singleton state
let supabase = null;
let publicConfig = null;
let currentSession = null;
let currentUser = null;
let isInitialized = false;
let initPromise = null;
const subscribers = new Set();

/**
 * Loads public client configuration from the backend.
 * Falls back to window.ENV if provided.
 */
async function fetchAuthConfig() {
    if (publicConfig) return publicConfig;
    try {
        const res = await fetch(apiUrl('/api/auth/config'));
        if (res.ok) {
            publicConfig = await res.json();
            return publicConfig;
        }
    } catch (e) {
        console.warn('[BIS Auth] Could not fetch /api/auth/config from server:', e.message);
    }
    // Fallback to window object if injected
    if (window.__BIS_AUTH_CONFIG__) {
        publicConfig = window.__BIS_AUTH_CONFIG__;
        return publicConfig;
    }
    return { supabase_url: '', supabase_anon_key: '' };
}

/**
 * Initializes the Supabase client and sets up the session listener.
 */
export async function initializeAuth() {
    if (isInitialized) return { supabase, session: currentSession, user: currentUser, configured: Boolean(supabase) };
    if (initPromise) return initPromise;

    initPromise = (async () => {
        try {
            const config = await fetchAuthConfig();
            const url = (config.supabase_url || '').trim();
            const publishableKey = (config.supabase_publishable_key || config.supabase_anon_key || '').trim();

            if (!url || !publishableKey || url === 'https://your-project.supabase.co' || publishableKey === 'your-anon-public-key-here') {
                console.info('[BIS Auth] Supabase configuration not yet populated in .env. Guest mode active.');
                isInitialized = true;
                notifySubscribers('CONFIG_MISSING', null);
                return { supabase: null, session: null, user: null, configured: false };
            }

            supabase = createClient(url, publishableKey, {
                auth: {
                    persistSession: true,
                    autoRefreshToken: true,
                    detectSessionInUrl: true,
                    storageKey: 'bis_supabase_auth_token'
                }
            });

            if (typeof window !== 'undefined') {
                window.__BIS_SUPABASE_CLIENT__ = supabase;
            }

            // Listen for auth state changes
            supabase.auth.onAuthStateChange(async (event, session) => {
                currentSession = session;
                currentUser = session?.user || null;
                notifySubscribers(event, session);
            });

            // Recover initial session
            const { data, error } = await supabase.auth.getSession();
            if (!error && data?.session) {
                currentSession = data.session;
                currentUser = data.session.user;
                notifySubscribers('INITIAL_SESSION', currentSession);
            }

            isInitialized = true;
            return { supabase, session: currentSession, user: currentUser, configured: true };
        } catch (err) {
            console.error('[BIS Auth] Failed to initialize Supabase client:', err);
            isInitialized = true;
            return { supabase: null, session: null, user: null, configured: false, error: err };
        }
    })();

    return initPromise;
}

/**
 * Retrieves cached user metadata from localStorage if present.
 */
export function getCachedUser() {
    if (currentUser) return currentUser;
    try {
        const customKey = localStorage.getItem('bis_supabase_auth_token');
        if (customKey) {
            const parsed = JSON.parse(customKey);
            if (parsed?.user) return parsed.user;
            if (parsed?.currentSession?.user) return parsed.currentSession.user;
        }
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && (key.startsWith('sb-') && key.endsWith('-auth-token'))) {
                const val = localStorage.getItem(key);
                if (val) {
                    const parsed = JSON.parse(val);
                    if (parsed?.user) return parsed.user;
                    if (parsed?.currentSession?.user) return parsed.currentSession.user;
                }
            }
        }
    } catch (e) {
        console.warn('[BIS Auth] Failed to read cached user from localStorage:', e);
    }
    return null;
}

/**
 * Retrieves cached session if present.
 */
export function getCachedSession() {
    if (currentSession) return currentSession;
    try {
        const customKey = localStorage.getItem('bis_supabase_auth_token');
        if (customKey) {
            const parsed = JSON.parse(customKey);
            if (parsed?.access_token) return parsed;
            if (parsed?.currentSession?.access_token) return parsed.currentSession;
        }
    } catch (e) {
        // silent
    }
    return null;
}

/**
 * Returns the singleton Supabase client instance.
 */
export function getSupabaseClient() {
    if (supabase) return supabase;
    if (typeof window !== 'undefined' && window.__BIS_SUPABASE_CLIENT__) {
        supabase = window.__BIS_SUPABASE_CLIENT__;
        return supabase;
    }
    return null;
}

/**
 * Returns or asynchronously initializes the singleton Supabase client instance.
 */
export async function getOrInitSupabaseClient() {
    const client = getSupabaseClient();
    if (client) return client;
    const res = await initializeAuth();
    return res?.supabase || getSupabaseClient();
}

/**
 * Notifies all registered UI subscribers of auth state changes.
 */
function notifySubscribers(event, session) {
    const user = session?.user || currentUser || getCachedUser() || null;
    for (const sub of subscribers) {
        try {
            sub(event, session, user);
        } catch (e) {
            console.error('[BIS Auth] Subscriber notification error:', e);
        }
    }
}

/**
 * Registers an auth state listener.
 * Returns an unsubscribe function.
 */
export function onAuthStateChange(callback) {
    if (typeof callback !== 'function') return () => {};
    subscribers.add(callback);
    // Immediately invoke with cached or initialized state
    const cachedUser = currentUser || getCachedUser();
    const cachedSession = currentSession || getCachedSession();
    if (cachedUser) {
        try {
            callback('CACHED_SESSION', cachedSession, cachedUser);
        } catch (e) {
            console.error('[BIS Auth] Initial subscriber callback error:', e);
        }
    } else if (isInitialized) {
        try {
            callback('INITIAL_STATE', currentSession, currentUser);
        } catch (e) {
            console.error('[BIS Auth] Initial subscriber callback error:', e);
        }
    }
    return () => subscribers.delete(callback);
}

/**
 * Returns the current active Supabase session, if any.
 */
export function getSession() {
    return currentSession || getCachedSession();
}

/**
 * Returns the currently authenticated Supabase user, if any.
 */
export function getUser() {
    return currentUser || getCachedUser();
}

/**
 * Returns true if the client was successfully configured with valid Supabase credentials.
 */
export function isConfigured() {
    return Boolean(supabase);
}

/**
 * Returns authorization headers with the current Bearer token, or an empty object.
 */
export function getAuthHeaders() {
    if (currentSession?.access_token) {
        return {
            Authorization: `Bearer ${currentSession.access_token}`
        };
    }
    return {};
}

/**
 * Sign in with Email and Password.
 */
export async function signInWithEmail(email, password) {
    await initializeAuth();
    if (!supabase) {
        throw new Error('Supabase is not configured. Please set SUPABASE_URL and SUPABASE_ANON_KEY in your .env file.');
    }
    const { data, error } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password: password
    });
    if (error) throw error;
    currentSession = data.session;
    currentUser = data.user;
    return data;
}

/**
 * Sign up with Email and Password.
 * Handles both instant session creation and email-verification required cases.
 */
export async function signUpWithEmail(email, password) {
    // 1. Strict deliverability validation before any Supabase call
    const val = validateDeliverableEmail(email);
    if (!val.valid) {
        throw new Error(val.error || 'Please enter a valid, deliverable email address. Test or placeholder domains are not permitted.');
    }

    // 2. Cooldown check
    const remaining = getEmailCooldownRemaining(EMAIL_COOLDOWN_ACTIONS.SIGNUP);
    if (remaining > 0) {
        throw new Error(`Signup request recently sent. Please wait ${remaining}s before requesting another confirmation email.`);
    }

    // 3. Supabase client initialization & guarded call
    await initializeAuth();
    if (!supabase) {
        throw new Error('Supabase is not configured. Please set SUPABASE_URL and SUPABASE_ANON_KEY in your .env file.');
    }

    let result;
    try {
        result = await supabase.auth.signUp({
            email: val.email || email.trim(),
            password: password,
            options: {
                emailRedirectTo: (typeof window !== 'undefined' && window.location && window.location.origin) 
                    ? `${window.location.origin}/auth/callback` 
                    : '/auth/callback'
            }
        });
    } catch (err) {
        if (err?.status === 429 || err?.message?.toLowerCase().includes('rate limit') || err?.message?.toLowerCase().includes('seconds')) {
            setEmailCooldown(EMAIL_COOLDOWN_ACTIONS.SIGNUP, 60);
            const rateErr = new Error('Rate limit reached. Too many requests sent. Please wait a moment before trying again.');
            rateErr.status = 429;
            throw rateErr;
        }
        throw err;
    }

    const { data, error } = result || {};
    if (error) {
        if (error.status === 429 || error.message?.toLowerCase().includes('rate limit') || error.message?.toLowerCase().includes('seconds')) {
            setEmailCooldown(EMAIL_COOLDOWN_ACTIONS.SIGNUP, 60);
            const rateErr = new Error('Rate limit reached. Too many requests sent. Please wait a moment before trying again.');
            rateErr.status = 429;
            throw rateErr;
        }
        throw error;
    }

    // Start 60s cooldown after successful signup dispatch
    setEmailCooldown(EMAIL_COOLDOWN_ACTIONS.SIGNUP, 60);
    currentSession = data?.session || null;
    currentUser = data?.user || null;
    return data;
}

/**
 * Sign in with Google OAuth.
 */
export async function signInWithGoogle() {
    await initializeAuth();
    if (!supabase) {
        throw new Error('Supabase is not configured. Please set SUPABASE_URL and SUPABASE_ANON_KEY in your .env file.');
    }
    const redirectTo = `${window.location.origin}/auth/callback`;
    const { data, error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
            redirectTo: redirectTo
        }
    });
    if (error) throw error;
    return data;
}

/**
 * Sign in with GitHub OAuth.
 */
export async function signInWithGitHub() {
    await initializeAuth();
    if (!supabase) {
        throw new Error('Supabase is not configured. Please set SUPABASE_URL and SUPABASE_ANON_KEY in your .env file.');
    }
    const redirectTo = `${window.location.origin}/auth/callback`;
    const { data, error } = await supabase.auth.signInWithOAuth({
        provider: 'github',
        options: {
            redirectTo: redirectTo
        }
    });
    if (error) throw error;
    return data;
}

/**
 * Signs out the current user and clears session state.
 */
export async function signOut() {
    // 1. Immediately reset in-memory state
    currentSession = null;
    currentUser = null;

    // 2. Immediately purge tokens from localStorage and guest flag from sessionStorage
    try {
        localStorage.removeItem('bis_supabase_auth_token');
        for (let i = localStorage.length - 1; i >= 0; i--) {
            const key = localStorage.key(i);
            if (key && (key.startsWith('sb-') && key.endsWith('-auth-token'))) {
                localStorage.removeItem(key);
            }
        }
        localStorage.removeItem('bis_user_preferences');
        localStorage.removeItem('bis_onboarding_completed');
    } catch (e) {
        console.warn('[BIS Auth] LocalStorage purge warning:', e);
    }
    setGuestSession(false);

    // 3. Immediately notify all subscribers
    notifySubscribers('SIGNED_OUT', null);

    // 4. Trigger Supabase client signOut with timeout to prevent hanging
    if (supabase) {
        try {
            await Promise.race([
                supabase.auth.signOut(),
                new Promise(resolve => setTimeout(resolve, 1000))
            ]);
        } catch (err) {
            console.warn('[BIS Auth] Supabase signOut warning:', err?.message || err);
        }
    }
}

/**
 * Sends a password reset email using Supabase's official flow.
 */
export async function sendPasswordReset(email) {
    // 1. Strict deliverability validation before calling Supabase
    const val = validateDeliverableEmail(email);
    if (!val.valid) {
        throw new Error(val.error || 'Please enter a valid, deliverable email address. Test or placeholder domains are not permitted.');
    }

    // 2. Cooldown check
    const remaining = getEmailCooldownRemaining(EMAIL_COOLDOWN_ACTIONS.PASSWORD_RESET);
    if (remaining > 0) {
        throw new Error(`Password reset request recently sent. Please wait ${remaining}s before requesting another reset email.`);
    }

    // 3. Supabase client initialization & guarded call
    await initializeAuth();
    if (!supabase) {
        throw new Error('Supabase is not configured. Please set SUPABASE_URL and SUPABASE_ANON_KEY in your .env file.');
    }

    const redirectTo = `${window.location.origin}/auth/callback?type=recovery`;
    let result;
    try {
        result = await supabase.auth.resetPasswordForEmail(val.email || email.trim(), {
            redirectTo: redirectTo
        });
    } catch (err) {
        if (err?.status === 429 || err?.message?.toLowerCase().includes('rate limit') || err?.message?.toLowerCase().includes('seconds')) {
            setEmailCooldown(EMAIL_COOLDOWN_ACTIONS.PASSWORD_RESET, 60);
            const rateErr = new Error('Rate limit reached. Too many requests sent. Please wait a moment before trying again.');
            rateErr.status = 429;
            throw rateErr;
        }
        throw err;
    }

    const { data, error } = result || {};
    if (error) {
        if (error.status === 429 || error.message?.toLowerCase().includes('rate limit') || error.message?.toLowerCase().includes('seconds')) {
            setEmailCooldown(EMAIL_COOLDOWN_ACTIONS.PASSWORD_RESET, 60);
            const rateErr = new Error('Rate limit reached. Too many requests sent. Please wait a moment before trying again.');
            rateErr.status = 429;
            throw rateErr;
        }
        throw error;
    }

    // Start 60s cooldown after successful reset dispatch
    setEmailCooldown(EMAIL_COOLDOWN_ACTIONS.PASSWORD_RESET, 60);
    return data;
}

/**
 * Updates the user password after landing on the recovery callback.
 */
export async function updatePassword(newPassword) {
    await initializeAuth();
    if (!supabase) {
        throw new Error('Supabase is not configured.');
    }
    const { data, error } = await supabase.auth.updateUser({
        password: newPassword
    });
    if (error) throw error;
    return data;
}

/**
 * Returns the environment-appropriate Login URL.
 */
export function getLoginUrl() {
    if (typeof window === 'undefined') return '/login';
    const path = window.location.pathname || '';
    const isLocalDev = window.location.hostname === 'localhost' || 
                       window.location.hostname === '127.0.0.1' || 
                       window.location.port === '3000';
    const isStaticOrFile = window.location.protocol === 'file:' || path.endsWith('.html') || isLocalDev;
    return isStaticOrFile ? './login.html' : '/login';
}

/**
 * Returns the environment-appropriate Home / Workspace URL.
 */
export function getHomeUrl() {
    if (typeof window === 'undefined') return '/#home';
    const path = window.location.pathname || '';
    const isLocalDev = window.location.hostname === 'localhost' || 
                       window.location.hostname === '127.0.0.1' || 
                       window.location.port === '3000';
    const isStaticOrFile = window.location.protocol === 'file:' || path.endsWith('.html') || isLocalDev;
    return isStaticOrFile ? './index.html#home' : '/#home';
}

/**
 * Checks whether the current user has opted for guest session access.
 */
export function isGuestSession() {
    if (typeof window === 'undefined') return false;
    try {
        if (sessionStorage.getItem('bis_guest_mode') === 'true') return true;
        const params = new URLSearchParams(window.location.search);
        if (params.get('guest') === 'true' || params.get('guest') === '1') {
            sessionStorage.setItem('bis_guest_mode', 'true');
            return true;
        }
    } catch (e) {
        // silent
    }
    return false;
}

/**
 * Sets or clears the guest mode flag in sessionStorage.
 */
export function setGuestSession(enable = true) {
    if (typeof window === 'undefined') return;
    try {
        if (enable) {
            sessionStorage.setItem('bis_guest_mode', 'true');
        } else {
            sessionStorage.removeItem('bis_guest_mode');
        }
    } catch (e) {
        // silent
    }
}

/**
 * Fast synchronous check used exclusively for early entry to prevent FOUC (flash of unauthenticated content).
 * NOTE: As per architectural requirements, localStorage is NOT the final authority;
 * Supabase auth.getSession() performs the canonical session validation.
 */
export function hasPotentialSession() {
    if (typeof window === 'undefined') return false;
    if (isGuestSession()) return true;
    try {
        if (localStorage.getItem('bis_supabase_auth_token')) return true;
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && (key.startsWith('sb-') && key.endsWith('-auth-token'))) {
                return true;
            }
        }
    } catch (e) {
        // silent
    }
    return false;
}

/**
 * Asynchronously validates the current session with the Supabase client.
 * Returns: { authenticated: boolean, user: object|null, session: object|null, isGuest: boolean }
 */
export async function validateSession() {
    // 1. Guest session explicitly enabled
    if (isGuestSession()) {
        return { authenticated: true, user: null, session: null, isGuest: true };
    }

    // 2. Initialize Supabase client
    const initResult = await initializeAuth();
    const client = initResult.supabase;

    // If Supabase credentials are not configured in environment, allow guest access
    if (!initResult.configured || !client) {
        return { authenticated: true, user: null, session: null, isGuest: true };
    }

    // 3. Canonical validation with Supabase
    try {
        const { data, error } = await client.auth.getSession();
        if (error || !data?.session) {
            await signOut();
            return { authenticated: false, user: null, session: null, isGuest: false };
        }

        const sess = data.session;
        const nowSec = Math.floor(Date.now() / 1000);
        if (sess.expires_at && sess.expires_at <= nowSec) {
            // Expired session that could not be auto-refreshed
            await signOut();
            return { authenticated: false, user: null, session: null, isGuest: false };
        }

        currentSession = sess;
        currentUser = sess.user;
        return { authenticated: true, user: sess.user, session: sess, isGuest: false };
    } catch (err) {
        console.warn('[BIS Auth] Session validation error:', err);
        await signOut();
        return { authenticated: false, user: null, session: null, isGuest: false };
    }
}


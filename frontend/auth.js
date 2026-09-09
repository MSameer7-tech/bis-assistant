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
    await initializeAuth();
    if (!supabase) {
        throw new Error('Supabase is not configured. Please set SUPABASE_URL and SUPABASE_ANON_KEY in your .env file.');
    }
    const { data, error } = await supabase.auth.signUp({
        email: email.trim(),
        password: password,
        options: {
            emailRedirectTo: (typeof window !== 'undefined' && window.location && window.location.origin) 
                ? `${window.location.origin}/auth/callback` 
                : '/auth/callback'
        }
    });
    if (error) throw error;
    currentSession = data.session;
    currentUser = data.user;
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
    await initializeAuth();
    if (!supabase) {
        throw new Error('Supabase is not configured. Please set SUPABASE_URL and SUPABASE_ANON_KEY in your .env file.');
    }
    const redirectTo = `${window.location.origin}/auth/callback?type=recovery`;
    const { data, error } = await supabase.auth.resetPasswordForEmail(email.trim(), {
        redirectTo: redirectTo
    });
    if (error) throw error;
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
    const isStaticOrFile = window.location.protocol === 'file:' || path.endsWith('.html');
    return isStaticOrFile ? './login.html' : '/login';
}

/**
 * Returns the environment-appropriate Home / Workspace URL.
 */
export function getHomeUrl() {
    if (typeof window === 'undefined') return '/#home';
    const path = window.location.pathname || '';
    const isStaticOrFile = window.location.protocol === 'file:' || path.endsWith('.html');
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


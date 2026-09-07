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
        const res = await fetch('/api/auth/config');
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
    return supabase;
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
            emailRedirectTo: `${window.location.origin}/auth/callback`
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

    // 2. Immediately purge tokens from localStorage
    try {
        localStorage.removeItem('bis_supabase_auth_token');
        for (let i = localStorage.length - 1; i >= 0; i--) {
            const key = localStorage.key(i);
            if (key && (key.startsWith('sb-') && key.endsWith('-auth-token'))) {
                localStorage.removeItem(key);
            }
        }
    } catch (e) {
        console.warn('[BIS Auth] LocalStorage purge warning:', e);
    }

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

/**
 * BIS AI Assistant - Supabase User Preferences Persistence Module
 *
 * Implements persistent user preferences using the existing Supabase client:
 * - Table: public.user_preferences
 * - User ID bound strictly to authenticated Supabase user identity (auth.uid())
 * - Fast local cache in localStorage (user-scoped: bis_user_preferences_<userId>)
 * - Backward-compatible global key (bis_user_preferences) tagged with _cached_user_id
 * - Non-blocking asynchronous database loading
 * - Graceful fallback when database is offline or unreachable
 * - Multi-user isolation: User A -> logout -> User B guarantees B never sees A's preferences
 * - Guest mode preservation: guest users persist locally only
 */

import { getSupabaseClient, getOrInitSupabaseClient, initializeAuth, getUser, isGuestSession, onAuthStateChange } from './auth.js?v=14.1.0';

// Canonical database values & UI display mappings
export const RESPONSE_STYLE_TO_CANONICAL = {
    'Quick & Simple': 'quick',
    'quick': 'quick',
    'simple': 'quick',
    'Detailed & Explanatory': 'detailed',
    'detailed': 'detailed',
    'explanatory': 'detailed',
    'Professional & Compliance-focused': 'professional',
    'professional': 'professional',
    'compliance': 'professional'
};

export const CANONICAL_TO_RESPONSE_STYLE = {
    'quick': 'Quick & Simple',
    'detailed': 'Detailed & Explanatory',
    'professional': 'Professional & Compliance-focused'
};

export function toCanonicalResponseStyle(style) {
    if (!style) return 'professional';
    const key = String(style).trim();
    return RESPONSE_STYLE_TO_CANONICAL[key] || RESPONSE_STYLE_TO_CANONICAL[key.toLowerCase()] || 'professional';
}

export function toUiResponseStyle(canonical) {
    if (!canonical) return 'Professional & Compliance-focused';
    const key = String(canonical).trim().toLowerCase();
    return CANONICAL_TO_RESPONSE_STYLE[key] || CANONICAL_TO_RESPONSE_STYLE[canonical] || 'Professional & Compliance-focused';
}

export const DEFAULT_USER_PREFERENCES = {
    role: null, // NEVER default to Manufacturer if missing/null
    useCases: ['Finding Indian Standards', 'Checking compliance requirements'],
    location: {
        country: 'India',
        state: 'Delhi (NCT)',
        city: 'New Delhi'
    },
    language: 'en',
    responseStyle: 'Professional & Compliance-focused', // default corresponds to canonical 'professional'
    onboarding_completed: false,
    completedAt: null
};

// In-memory active preference cache
let activePreferences = null;
let activeUserId = null;

/**
 * Normalizes a Supabase database row into the frontend preference structure.
 */
export function normalizeDbToFrontend(dbRow) {
    if (!dbRow || typeof dbRow !== 'object') return null;

    let useCases = [];
    if (Array.isArray(dbRow.use_cases)) {
        useCases = dbRow.use_cases;
    } else if (typeof dbRow.use_cases === 'string') {
        try {
            const parsed = JSON.parse(dbRow.use_cases);
            if (Array.isArray(parsed)) useCases = parsed;
        } catch (e) {
            useCases = [];
        }
    }

    // Role: strictly preserve null/empty, NEVER invent "Manufacturer"
    const role = (dbRow.role && typeof dbRow.role === 'string' && dbRow.role.trim())
        ? dbRow.role.trim()
        : null;

    return {
        role: role,
        useCases: useCases,
        location: {
            country: dbRow.country || 'India',
            state: dbRow.state || 'Delhi (NCT)',
            city: dbRow.city || 'New Delhi'
        },
        language: dbRow.language || 'en',
        responseStyle: toUiResponseStyle(dbRow.response_style),
        onboarding_completed: dbRow.onboarding_completed === true,
        completedAt: dbRow.updated_at || dbRow.created_at || null
    };
}

/**
 * Normalizes frontend preferences into the Supabase database schema row.
 */
export function normalizeFrontendToDb(prefs, userId) {
    if (!prefs) prefs = {};
    const useCases = Array.isArray(prefs.useCases)
        ? prefs.useCases
        : (Array.isArray(prefs.bis_use_cases) ? prefs.bis_use_cases : []);

    const role = (prefs.role && typeof prefs.role === 'string' && prefs.role.trim())
        ? prefs.role.trim()
        : null;

    return {
        user_id: userId,
        role: role,
        use_cases: useCases,
        country: prefs.location?.country || null,
        state: prefs.location?.state || null,
        city: prefs.location?.city || null,
        language: prefs.language || 'en',
        response_style: toCanonicalResponseStyle(prefs.responseStyle),
        onboarding_completed: Boolean(prefs.onboarding_completed),
        updated_at: new Date().toISOString()
    };
}

/**
 * Returns user-scoped LocalStorage key.
 */
export function getUserCacheKey(userId) {
    return userId ? `bis_user_preferences_${userId}` : 'bis_user_preferences';
}

/**
 * Returns user-scoped onboarding key.
 */
export function getUserOnboardingKey(userId) {
    return userId ? `bis_onboarding_completed_${userId}` : 'bis_onboarding_completed';
}

/**
 * Synchronously retrieves user preferences.
 * Uses in-memory cache if matching user, otherwise checks user-scoped LocalStorage.
 * Prevents cross-user leakage by ignoring cache belonging to a different user_id.
 */
export function getUserPreferences(explicitUserId = null) {
    const user = getUser();
    const userId = explicitUserId || user?.id || null;

    // Check in-memory cache if belonging to current user context
    if (activePreferences && activeUserId === userId) {
        return { ...DEFAULT_USER_PREFERENCES, ...activePreferences };
    }

    try {
        if (userId && !isGuestSession()) {
            // Check user-scoped cache key
            const scopedRaw = localStorage.getItem(getUserCacheKey(userId));
            if (scopedRaw) {
                const parsed = JSON.parse(scopedRaw);
                activePreferences = parsed;
                activeUserId = userId;
                return { ...DEFAULT_USER_PREFERENCES, ...parsed };
            }

            // Check global key with safety check for _cached_user_id
            const globalRaw = localStorage.getItem('bis_user_preferences');
            if (globalRaw) {
                const parsed = JSON.parse(globalRaw);
                if (parsed._cached_user_id === userId) {
                    activePreferences = parsed;
                    activeUserId = userId;
                    return { ...DEFAULT_USER_PREFERENCES, ...parsed };
                }
                // Stale data belonging to another user or guest -> DO NOT LEAK!
            }
            return { ...DEFAULT_USER_PREFERENCES };
        } else {
            // Guest mode
            const guestRaw = localStorage.getItem('bis_user_preferences');
            if (guestRaw) {
                const parsed = JSON.parse(guestRaw);
                // Ensure not returning authenticated user's cached data to guest
                if (!parsed._cached_user_id || parsed._cached_user_id === 'guest') {
                    return { ...DEFAULT_USER_PREFERENCES, ...parsed };
                }
            }
            return { ...DEFAULT_USER_PREFERENCES };
        }
    } catch (e) {
        console.warn('[BIS Preferences] Error reading preferences from cache:', e);
    }
    return { ...DEFAULT_USER_PREFERENCES };
}

/**
 * Saves user preferences locally and initiates background Supabase sync for authenticated users.
 */
export function saveUserPreferences(prefs, explicitUserId = null) {
    const user = getUser();
    const userId = explicitUserId || user?.id || null;
    const isGuest = isGuestSession() || !userId;

    const merged = {
        ...DEFAULT_USER_PREFERENCES,
        ...prefs,
        onboarding_completed: true,
        completedAt: new Date().toISOString()
    };

    activePreferences = merged;
    activeUserId = userId;

    try {
        if (userId && !isGuest) {
            // Save to user-scoped key
            const scopedPayload = { ...merged, _cached_user_id: userId };
            localStorage.setItem(getUserCacheKey(userId), JSON.stringify(scopedPayload));
            localStorage.setItem(getUserOnboardingKey(userId), 'true');

            // Also maintain global key tagged with _cached_user_id for backward compatibility
            localStorage.setItem('bis_user_preferences', JSON.stringify(scopedPayload));
            localStorage.setItem('bis_onboarding_completed', 'true');

            // Asynchronously sync to Supabase database (non-blocking)
            upsertUserPreferencesToSupabase(userId, merged).catch(err => {
                console.warn('[BIS Preferences] Background database sync warning:', err?.message || err);
            });
        } else {
            // Guest mode
            const guestPayload = { ...merged, _cached_user_id: 'guest' };
            localStorage.setItem('bis_user_preferences', JSON.stringify(guestPayload));
            localStorage.setItem('bis_onboarding_completed', 'true');
        }
    } catch (e) {
        console.warn('[BIS Preferences] Error caching preferences:', e);
    }

    return merged;
}

/**
 * Loads preferences from Supabase for the authenticated user.
 * Non-blocking async fetch with 3000ms network timeout.
 * Returns normalized preferences or null if no record exists.
 */
export async function loadUserPreferencesFromSupabase(userId) {
    if (!userId) {
        const user = getUser();
        userId = user?.id;
    }
    if (!userId || isGuestSession()) {
        return getUserPreferences(userId);
    }

    try {
        let client = getSupabaseClient();
        if (!client && typeof initializeAuth === 'function') {
            const initRes = await initializeAuth();
            client = initRes?.supabase || getSupabaseClient();
        }
        if (!client && typeof getOrInitSupabaseClient === 'function') {
            client = await getOrInitSupabaseClient();
        }

        console.log('[BIS Preferences] authenticated user detected:', Boolean(userId));
        console.log('[BIS Preferences] user id available:', Boolean(userId));
        console.log('[BIS Preferences] Supabase client available:', Boolean(client));

        if (!client) {
            console.info('[BIS Preferences] Supabase client not available, using local cache.');
            return getUserPreferences(userId);
        }

        // Query public.user_preferences for user_id with 3000ms timeout
        const queryPromise = client
            .from('user_preferences')
            .select('user_id, role, use_cases, country, state, city, language, response_style, onboarding_completed, created_at, updated_at')
            .eq('user_id', userId)
            .maybeSingle();

        const timeoutPromise = new Promise((_, reject) =>
            setTimeout(() => reject(new Error('Preferences database request timeout')), 3000)
        );

        const { data, error } = await Promise.race([queryPromise, timeoutPromise]);

        if (error) {
            console.warn('[BIS Preferences] Supabase query error (retaining local cache):', error.message || error);
            return getUserPreferences(userId);
        }

        if (data) {
            // Database record found! Database is the source of truth
            const normalized = normalizeDbToFrontend(data);
            activePreferences = normalized;
            activeUserId = userId;

            try {
                const scopedPayload = { ...normalized, _cached_user_id: userId };
                localStorage.setItem(getUserCacheKey(userId), JSON.stringify(scopedPayload));
                localStorage.setItem('bis_user_preferences', JSON.stringify(scopedPayload));

                if (normalized.onboarding_completed) {
                    localStorage.setItem(getUserOnboardingKey(userId), 'true');
                    localStorage.setItem('bis_onboarding_completed', 'true');
                } else {
                    localStorage.removeItem(getUserOnboardingKey(userId));
                    localStorage.removeItem('bis_onboarding_completed');
                }
            } catch (storageErr) {
                console.warn('[BIS Preferences] Cache update warning:', storageErr);
            }

            return normalized;
        }

        // No database record exists yet for this authenticated user
        return null;
    } catch (err) {
        console.warn('[BIS Preferences] Network or timeout error during load (retaining cache):', err?.message || err);
        return getUserPreferences(userId);
    }
}

/**
 * Upserts user preferences to Supabase public.user_preferences.
 * Uses auth.uid() identity guarantee via authenticated client session.
 */
export async function upsertUserPreferencesToSupabase(userId, prefs) {
    if (!userId) {
        const user = getUser();
        userId = user?.id;
    }
    if (!userId || isGuestSession()) {
        return null;
    }

    const dbRow = normalizeFrontendToDb(prefs, userId);

    try {
        let client = getSupabaseClient();
        if (!client && typeof initializeAuth === 'function') {
            const initRes = await initializeAuth();
            client = initRes?.supabase || getSupabaseClient();
        }
        if (!client && typeof getOrInitSupabaseClient === 'function') {
            client = await getOrInitSupabaseClient();
        }

        console.log('[BIS Preferences] authenticated user detected:', Boolean(userId));
        console.log('[BIS Preferences] user id available:', Boolean(userId));
        console.log('[BIS Preferences] Supabase client available:', Boolean(client));

        if (!client) {
            console.info('[BIS Preferences] Supabase client not available, skipping DB sync.');
            return null;
        }

        console.log('[BIS Preferences] preference upsert starting');

        const upsertPromise = client
            .from('user_preferences')
            .upsert(dbRow, { onConflict: 'user_id' });

        const timeoutPromise = new Promise((_, reject) =>
            setTimeout(() => reject(new Error('Preferences database upsert timeout')), 3000)
        );

        const { error } = await Promise.race([upsertPromise, timeoutPromise]);

        if (error) {
            console.warn('[BIS Preferences] Database upsert error:', error.message || error);
            console.log('[BIS Preferences] preference upsert completed: failure');
            return null;
        }

        console.log('[BIS Preferences] preference upsert completed: success');
        return dbRow;
    } catch (err) {
        console.warn('[BIS Preferences] Failed to upsert preferences to Supabase:', err?.message || err);
        console.log('[BIS Preferences] preference upsert completed: failure');
        return null;
    }
}

/**
 * Clears authenticated preference state from memory and local cache.
 * Must be invoked on signOut to prevent cross-user data leakage.
 */
export function clearAuthenticatedPreferences() {
    activePreferences = null;
    activeUserId = null;
    try {
        localStorage.removeItem('bis_user_preferences');
        localStorage.removeItem('bis_onboarding_completed');
    } catch (e) {
        // silent
    }
}

// Subscribe to auth state changes to clear cache on signOut
try {
    onAuthStateChange((event) => {
        if (event === 'SIGNED_OUT') {
            clearAuthenticatedPreferences();
        }
    });
} catch (e) {
    // silent
}

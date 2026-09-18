/**
 * BIS AI Assistant - Supabase Conversation & Message Persistence Module
 *
 * Implements persistent chat storage to existing Supabase tables:
 * - public.conversations (id uuid, user_id uuid, title text, created_at timestamptz, updated_at timestamptz)
 * - public.messages (id uuid, conversation_id uuid, user_id uuid, role text, content text, metadata json, created_at timestamptz)
 *
 * Architecture & Guarantees:
 * - Zero schema modifications: binds strictly to existing Supabase tables & RLS policies.
 * - Authenticated users persist conversations & messages to Supabase.
 * - Guest mode uses localStorage only (0 Supabase database requests).
 * - Non-blocking async execution: local cache (localStorage) renders instantly; Supabase sync runs in background.
 * - RFC4122 v4 UUID compliance for all conversation and message IDs.
 */

import { getSupabaseClient, getOrInitSupabaseClient, getUser, getCachedUser, isGuestSession } from './auth.js';

/**
 * Generates an RFC4122 version 4 compliant UUID.
 */
export function generateUUID() {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
        return crypto.randomUUID();
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

/**
 * Validates if a string is a standard UUID.
 */
export function isUUID(str) {
    if (!str || typeof str !== 'string') return false;
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(str);
}

/**
 * Returns current authenticated user ID, or null if guest or unauthenticated.
 */
export function getAuthenticatedUserId() {
    if (isGuestSession()) return null;
    const user = getUser() || getCachedUser();
    return user?.id || null;
}

/**
 * Upserts a conversation record into public.conversations in Supabase.
 */
export async function upsertConversationToSupabase(conv, userId) {
    if (!userId || isGuestSession()) return { data: null, error: null };
    if (!conv || !conv.id) return { data: null, error: new Error('Invalid conversation object') };

    // Ensure valid UUID for Supabase
    if (!isUUID(conv.id)) {
        console.warn('[BIS Conversations] Cannot upsert non-UUID conversation ID to Supabase:', conv.id);
        return { data: null, error: new Error('Non-UUID conversation ID') };
    }

    try {
        let client = getSupabaseClient();
        if (!client) client = await getOrInitSupabaseClient();
        if (!client) {
            console.warn('[BIS Conversations] Supabase client unavailable for conversation upsert');
            return { data: null, error: new Error('Supabase client unavailable') };
        }

        const payload = {
            id: conv.id,
            user_id: userId,
            title: (conv.title || 'New Session').trim().slice(0, 500),
            updated_at: new Date().toISOString()
        };

        if (conv.createdAt) {
            payload.created_at = new Date(conv.createdAt).toISOString();
        }

        const { data, error } = await client
            .from('conversations')
            .upsert(payload, { onConflict: 'id' })
            .select()
            .single();

        if (error) {
            console.error('[BIS Conversations] Error upserting conversation to Supabase:', error.message || error);
            return { data: null, error };
        }

        return { data, error: null };
    } catch (err) {
        console.error('[BIS Conversations] Unexpected error during conversation upsert:', err);
        return { data: null, error: err };
    }
}

/**
 * Inserts a single message record into public.messages in Supabase.
 */
export async function insertMessageToSupabase(msg, conversationId, userId) {
    if (!userId || isGuestSession()) return { data: null, error: null };
    if (!conversationId || !isUUID(conversationId)) {
        console.warn('[BIS Conversations] Skipping message insert due to invalid conversationId:', conversationId);
        return { data: null, error: new Error('Invalid conversation ID') };
    }

    try {
        let client = getSupabaseClient();
        if (!client) client = await getOrInitSupabaseClient();
        if (!client) {
            console.warn('[BIS Conversations] Supabase client unavailable for message insert');
            return { data: null, error: new Error('Supabase client unavailable') };
        }

        const messageId = msg.id && isUUID(msg.id) ? msg.id : generateUUID();
        // Ensure the message object in memory retains this UUID
        msg.id = messageId;

        const payload = {
            id: messageId,
            conversation_id: conversationId,
            user_id: userId,
            role: msg.role || 'user',
            content: msg.text || msg.content || '',
            metadata: (msg.data || msg.metadata) ? (msg.data || msg.metadata) : {}
        };

        if (msg.createdAt || msg.created_at) {
            payload.created_at = new Date(msg.createdAt || msg.created_at).toISOString();
        }

        const { data, error } = await client
            .from('messages')
            .insert(payload)
            .select()
            .single();

        if (error) {
            console.error('[BIS Conversations] Error inserting message to Supabase:', error.message || error);
            return { data: null, error };
        }

        return { data, error: null };
    } catch (err) {
        console.error('[BIS Conversations] Unexpected error during message insert:', err);
        return { data: null, error: err };
    }
}

/**
 * Loads all conversations and their messages from Supabase for the authenticated user.
 * Returns normalized conversation array compatible with frontend state.
 */
export async function loadConversationsFromSupabase(userId) {
    if (!userId || isGuestSession()) return null;

    try {
        let client = getSupabaseClient();
        if (!client) client = await getOrInitSupabaseClient();
        if (!client) {
            console.warn('[BIS Conversations] Supabase client unavailable for loading conversations');
            return null;
        }

        // 1. Fetch conversations ordered by latest activity
        const convPromise = client
            .from('conversations')
            .select('id, user_id, title, created_at, updated_at')
            .eq('user_id', userId)
            .order('updated_at', { ascending: false });

        // 2. Fetch all messages for the user ordered chronologically
        const msgPromise = client
            .from('messages')
            .select('id, conversation_id, user_id, role, content, metadata, created_at')
            .eq('user_id', userId)
            .order('created_at', { ascending: true });

        // Add 5000ms timeout race to prevent blocking
        const timeoutPromise = new Promise((_, reject) =>
            setTimeout(() => reject(new Error('Supabase conversations fetch timeout')), 5000)
        );

        const [{ data: convRows, error: convErr }, { data: msgRows, error: msgErr }] = await Promise.race([
            Promise.all([convPromise, msgPromise]),
            timeoutPromise
        ]);

        if (convErr) {
            console.warn('[BIS Conversations] Error querying conversations:', convErr.message || convErr);
            return null;
        }
        if (msgErr) {
            console.warn('[BIS Conversations] Error querying messages:', msgErr.message || msgErr);
            return null;
        }

        if (!convRows || convRows.length === 0) {
            return [];
        }

        // Group messages by conversation_id
        const messagesByConv = {};
        (msgRows || []).forEach(m => {
            const cid = m.conversation_id;
            if (!messagesByConv[cid]) messagesByConv[cid] = [];
            messagesByConv[cid].push({
                id: m.id,
                role: m.role,
                text: m.content || '',
                data: m.metadata || undefined,
                createdAt: m.created_at ? new Date(m.created_at).getTime() : Date.now()
            });
        });

        // Assemble normalized conversation objects
        const normalized = convRows.map(c => ({
            id: c.id,
            title: c.title || 'New Session',
            createdAt: c.created_at ? new Date(c.created_at).getTime() : Date.now(),
            updatedAt: c.updated_at ? new Date(c.updated_at).getTime() : Date.now(),
            messages: messagesByConv[c.id] || []
        }));

        console.info(`[BIS Conversations] Successfully restored ${normalized.length} conversations from Supabase.`);
        return normalized;
    } catch (err) {
        console.warn('[BIS Conversations] Failed to load conversations from Supabase:', err);
        return null;
    }
}

/**
 * Deletes a conversation and its messages from Supabase.
 */
export async function deleteConversationFromSupabase(convId, userId) {
    if (!userId || isGuestSession() || !convId || !isUUID(convId)) return;

    try {
        let client = getSupabaseClient();
        if (!client) client = await getOrInitSupabaseClient();
        if (!client) return;

        // Delete messages first, then conversation
        await client.from('messages').delete().eq('conversation_id', convId).eq('user_id', userId);
        await client.from('conversations').delete().eq('id', convId).eq('user_id', userId);
        console.info('[BIS Conversations] Deleted conversation from Supabase:', convId);
    } catch (err) {
        console.warn('[BIS Conversations] Error deleting conversation from Supabase:', err);
    }
}

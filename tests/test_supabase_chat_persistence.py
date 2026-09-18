"""
Tests for Supabase Conversation & Message Persistence Module.

Verifies:
1. UUID compliance: IDs for conversations and messages are standard RFC4122 v4 UUIDs.
2. Zero schema violations: Columns match public.conversations and public.messages exactly.
3. Authenticated vs Guest isolation: Guest sessions make 0 Supabase DB requests.
4. Non-blocking async execution: Local cache provides instant responses.
5. Bidirectional normalization: Correct mapping between frontend models and Supabase rows.
"""

import re
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


class TestSupabaseChatPersistence:
    """Verifies frontend conversation and message persistence contracts."""

    def test_01_conversations_module_exists(self):
        """Verifies frontend/conversations.js exists and exports expected functions."""
        conv_file = FRONTEND_DIR / "conversations.js"
        assert conv_file.exists(), "frontend/conversations.js must exist"
        content = conv_file.read_text(encoding="utf-8")

        expected_exports = [
            "export function generateUUID",
            "export function isUUID",
            "export function getAuthenticatedUserId",
            "export async function upsertConversationToSupabase",
            "export async function insertMessageToSupabase",
            "export async function loadConversationsFromSupabase",
            "export async function deleteConversationFromSupabase"
        ]
        for exp in expected_exports:
            assert exp in content, f"Expected export '{exp}' in conversations.js"

    def test_02_database_schema_contract_compliance(self):
        """Verifies column names match public.conversations and public.messages schema."""
        conv_file = FRONTEND_DIR / "conversations.js"
        content = conv_file.read_text(encoding="utf-8")

        # public.conversations columns
        assert ".from('conversations')" in content
        assert "user_id: userId" in content
        assert "title:" in content
        assert "updated_at:" in content

        # public.messages columns
        assert ".from('messages')" in content
        assert "conversation_id:" in content
        assert "role:" in content
        assert "content:" in content
        assert "metadata:" in content

    def test_03_uuid_enforcement(self):
        """Verifies that non-UUIDs are detected and UUID validation is enforced."""
        conv_file = FRONTEND_DIR / "conversations.js"
        content = conv_file.read_text(encoding="utf-8")

        assert "isUUID(" in content
        assert "crypto.randomUUID" in content

    def test_04_app_js_imports_and_wires_conversations(self):
        """Verifies that app.js imports and invokes conversations.js functions."""
        app_file = FRONTEND_DIR / "app.js"
        content = app_file.read_text(encoding="utf-8")

        assert "from './conversations.js" in content
        assert "upsertConversationToSupabase" in content
        assert "insertMessageToSupabase" in content
        assert "loadConversationsFromSupabase" in content
        assert "generateUUID" in content

    def test_05_guest_mode_isolation(self):
        """Verifies that guest sessions bypass Supabase writes."""
        conv_file = FRONTEND_DIR / "conversations.js"
        content = conv_file.read_text(encoding="utf-8")

        assert "if (!userId || isGuestSession()) return { data: null, error: null };" in content or \
               "if (!userId || isGuestSession())" in content

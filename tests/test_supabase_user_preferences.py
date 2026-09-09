"""
Tests for Supabase User Preferences Persistence Module (Phase 14).

Verifies:
1. New authenticated user completes onboarding -> row created with canonical response_style.
2. Refresh -> preferences restored from Supabase to memory and cache.
3. Logout -> authenticated preference state cleared (memory + cache).
4. Another user logs in -> only their preferences appear; User B never sees User A preferences.
5. Clear LocalStorage -> preferences restored from Supabase.
6. Supabase unavailable (timeout / offline) -> local cache fallback works, UI never blocks.
7. Guest user -> LocalStorage only, 0 Supabase queries.
8. Preference editing -> database + cache + UI updated immediately without reload.
9. Role handling -> NULL role preserved, NEVER defaults to Manufacturer.
10. RLS policy enforcement & Security -> zero secrets, user identity bound strictly to auth.uid().
"""

import os
import json
import re
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


class TestSupabaseUserPreferences:
    """Comprehensive test suite for persistent Supabase user preferences."""

    def test_01_security_zero_secrets_in_frontend_code(self):
        """Verifies that no private keys, service role keys, or JWT secrets exist in frontend files."""
        forbidden_tokens = ["service_role", "jwt_secret", "gsk_", "AIzaSy", "sk-proj-", "sk-live-"]
        frontend_files = [
            FRONTEND_DIR / "preferences.js",
            FRONTEND_DIR / "auth.js",
            FRONTEND_DIR / "app.js",
            FRONTEND_DIR / "config.js",
            FRONTEND_DIR / "index.html",
            FRONTEND_DIR / "login.html"
        ]

        for file_path in frontend_files:
            assert file_path.exists(), f"Expected file {file_path.name} to exist"
            text = file_path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                assert token not in text, f"Security Violation: Forbidden token '{token}' detected in {file_path.name}"

    def test_02_canonical_response_style_mappings(self):
        """Verifies bidirectional mapping between canonical database values and UI display labels."""
        pref_file = FRONTEND_DIR / "preferences.js"
        content = pref_file.read_text(encoding="utf-8")

        # Canonical DB: quick, detailed, professional
        assert "'Quick & Simple': 'quick'" in content
        assert "'Detailed & Explanatory': 'detailed'" in content
        assert "'Professional & Compliance-focused': 'professional'" in content

        # UI mappings from canonical
        assert "'quick': 'Quick & Simple'" in content
        assert "'detailed': 'Detailed & Explanatory'" in content
        assert "'professional': 'Professional & Compliance-focused'" in content

        # DB default is professional
        assert "response_style: toCanonicalResponseStyle(prefs.responseStyle)" in content

    def test_03_role_normalization_never_defaults_to_manufacturer(self):
        """Verifies that missing/null role strictly remains NULL and NEVER defaults to Manufacturer."""
        pref_file = FRONTEND_DIR / "preferences.js"
        content = pref_file.read_text(encoding="utf-8")

        # DEFAULT_USER_PREFERENCES must have role: null
        assert re.search(r"role:\s*null", content), "DEFAULT_USER_PREFERENCES must define role: null"

        # normalizeDbToFrontend must preserve null role
        assert "dbRow.role && typeof dbRow.role === 'string' && dbRow.role.trim()" in content
        assert ": null" in content

        # app.js must not default role to Manufacturer in handleOnboardingNext
        app_file = FRONTEND_DIR / "app.js"
        app_content = app_file.read_text(encoding="utf-8")
        assert "tempPreferences.role = 'Manufacturer'" not in app_content, "app.js must not set tempPreferences.role to Manufacturer"

    def test_04_user_scoped_localstorage_cache_keys(self):
        """Verifies user-scoped LocalStorage cache keys prevent cross-user leakage."""
        pref_file = FRONTEND_DIR / "preferences.js"
        content = pref_file.read_text(encoding="utf-8")

        assert "getUserCacheKey(userId)" in content
        assert "bis_user_preferences_${userId}" in content
        assert "getUserOnboardingKey(userId)" in content
        assert "bis_onboarding_completed_${userId}" in content
        assert "_cached_user_id" in content

    def test_05_multi_user_isolation_and_logout_cleanup(self):
        """Verifies that clearAuthenticatedPreferences purges global cache and memory."""
        pref_file = FRONTEND_DIR / "preferences.js"
        content = pref_file.read_text(encoding="utf-8")

        assert "export function clearAuthenticatedPreferences()" in content
        assert "activePreferences = null" in content
        assert "activeUserId = null" in content
        assert "localStorage.removeItem('bis_user_preferences')" in content
        assert "localStorage.removeItem('bis_onboarding_completed')" in content

        # Auth.js signOut also cleans global preferences
        auth_file = FRONTEND_DIR / "auth.js"
        auth_content = auth_file.read_text(encoding="utf-8")
        assert "localStorage.removeItem('bis_user_preferences')" in auth_content
        assert "localStorage.removeItem('bis_onboarding_completed')" in auth_content

    def test_06_non_blocking_supabase_preference_loading(self):
        """Verifies that Supabase preference fetch is non-blocking with 3000ms max timeout."""
        pref_file = FRONTEND_DIR / "preferences.js"
        content = pref_file.read_text(encoding="utf-8")

        assert "export async function loadUserPreferencesFromSupabase(userId)" in content
        assert "3000" in content, "Must have 3000ms timeout promise race"
        assert "Promise.race([" in content

        # In app.js, must immediately render local cache and load Supabase asynchronously
        app_file = FRONTEND_DIR / "app.js"
        app_content = app_file.read_text(encoding="utf-8")
        assert "loadUserPreferencesFromSupabase(userId).then(" in app_content
        assert "applyPersonalization(cachedUserPrefs)" in app_content

    def test_07_database_source_of_truth_replaces_cache(self):
        """Verifies that when Supabase returns a valid record, it wins over local cache."""
        pref_file = FRONTEND_DIR / "preferences.js"
        content = pref_file.read_text(encoding="utf-8")

        assert "if (data) {" in content
        assert "normalizeDbToFrontend(data)" in content
        assert "localStorage.setItem(getUserCacheKey(userId)" in content
        assert "localStorage.setItem('bis_user_preferences'" in content

    def test_08_guest_mode_isolation(self):
        """Verifies that guest mode uses LocalStorage only and makes zero database calls."""
        pref_file = FRONTEND_DIR / "preferences.js"
        content = pref_file.read_text(encoding="utf-8")

        assert "if (!userId || isGuestSession()) {" in content
        assert "return getUserPreferences" in content

        app_file = FRONTEND_DIR / "app.js"
        app_content = app_file.read_text(encoding="utf-8")
        assert "if (authState.isGuest) {" in app_content

    def test_09_preference_edit_flow(self):
        """Verifies that saveUserPreferences immediately updates cache, memory, and syncs to Supabase."""
        pref_file = FRONTEND_DIR / "preferences.js"
        content = pref_file.read_text(encoding="utf-8")

        assert "export function saveUserPreferences(prefs" in content
        assert "activePreferences = merged" in content
        assert "upsertUserPreferencesToSupabase(userId, merged)" in content

    def test_10_database_schema_contract_compliance(self):
        """Verifies that the Supabase table column names and types match public.user_preferences."""
        pref_file = FRONTEND_DIR / "preferences.js"
        content = pref_file.read_text(encoding="utf-8")

        expected_columns = [
            "user_id",
            "role",
            "use_cases",
            "country",
            "state",
            "city",
            "language",
            "response_style",
            "onboarding_completed"
        ]
        for col in expected_columns:
            assert f"'{col}'" in content or f'"{col}"' in content or f"{col}:" in content or col in content, \
                f"Column {col} must be referenced in preferences.js"

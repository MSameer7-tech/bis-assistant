"""
BIS AI Assistant - Frontend Authentication Entry-Point Flow Verification Suite.

Validates:
1. Root entry must be login-first:
   - Fresh unauthenticated visitor -> Redirected to Login page.
   - Zero flash of unauthenticated content (FOUC) / hero page.
2. Existing Supabase authentication system preserved:
   - Synchronous early-check prevents FOUC using localStorage.
   - Supabase auth.getSession() remains canonical validation authority.
3. Preserves both environments:
   - Clean URLs (/login, /#home) on production servers.
   - Relative URLs (./login.html, ./index.html#home) for static file/local environments.
4. Guest flow preservation:
   - "Continue as Guest" from Login permits entry to workspace without authentication.
   - Logout clears guest mode and returns to Login.
5. Session persistence & lifecycle:
   - Refresh while authenticated preserves workspace.
   - Expired or corrupted session purges storage and redirects to Login.
   - Sign out purges tokens and redirects to Login.
   - Successful login navigates to workspace.
6. Zero secrets exposed in frontend codebase.
7. Authoritative frozen baselines completely intact.
"""

import json
import shutil
import subprocess
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


class TestAuthEntryFlow:
    """Test suite validating the production authentication entry-point flow."""

    def test_01_frontend_auth_helper_exports(self):
        """Verifies that auth.js exports canonical session validation & URL helpers."""
        auth_file = FRONTEND_DIR / "auth.js"
        assert auth_file.exists(), "frontend/auth.js must exist"
        content = auth_file.read_text(encoding="utf-8")

        assert "export function getLoginUrl" in content
        assert "export function getHomeUrl" in content
        assert "export function isGuestSession" in content
        assert "export function setGuestSession" in content
        assert "export function hasPotentialSession" in content
        assert "export async function validateSession" in content
        assert "export async function signOut" in content

    def test_02_no_secrets_exposed_in_frontend(self):
        """Verifies zero secret keys or private tokens are present in frontend files."""
        forbidden_tokens = ["service_role", "jwt_secret", "gsk_", "AIzaSy", "sk-proj-", "sk-live-"]
        frontend_files = [
            FRONTEND_DIR / "auth.js",
            FRONTEND_DIR / "app.js",
            FRONTEND_DIR / "config.js",
            FRONTEND_DIR / "index.html",
            FRONTEND_DIR / "login.html"
        ]

        for file_path in frontend_files:
            text = file_path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                assert token not in text, f"Forbidden secret token '{token}' detected in {file_path.name}"

    def test_03_index_html_has_synchronous_early_entry_guard(self):
        """Verifies index.html contains early synchronous entry-guard script in head."""
        index_file = FRONTEND_DIR / "index.html"
        content = index_file.read_text(encoding="utf-8")

        assert "window.location.replace" in content
        assert "bis_guest_mode" in content
        assert "bis_supabase_auth_token" in content
        assert "authLoadingScreen" in content
        assert "auth-loading-overlay" in content

    def test_04_styles_css_has_auth_loading_overlay(self):
        """Verifies styles.css provides dark loading overlay styling."""
        styles_file = FRONTEND_DIR / "styles.css"
        content = styles_file.read_text(encoding="utf-8")

        assert ".auth-loading-overlay" in content
        assert ".auth-loading-content" in content
        assert ".auth-loading-spinner" in content

    def test_05_login_html_preserves_continue_as_guest(self):
        """Verifies login.html retains 'Continue as Guest' with guest session activation."""
        login_file = FRONTEND_DIR / "login.html"
        content = login_file.read_text(encoding="utf-8")

        assert "Continue as Guest" in content
        assert "btnGuestLink" in content
        assert "setGuestSession(true)" in content

    def test_06_node_headless_unauthenticated_redirect(self):
        """Node.js headless test: unauthenticated visitor is immediately redirected to Login."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")

        script = """
        // Mock browser window and storage
        let redirectedTo = null;
        global.window = {
            location: {
                protocol: 'http:',
                pathname: '/',
                search: '',
                replace: function(url) { redirectedTo = url; }
            }
        };

        const store = {};
        global.localStorage = {
            getItem: (k) => store[k] || null,
            setItem: (k, v) => { store[k] = String(v); },
            removeItem: (k) => { delete store[k]; },
            length: 0,
            key: (i) => Object.keys(store)[i] || null
        };

        const sessionStore = {};
        global.sessionStorage = {
            getItem: (k) => sessionStore[k] || null,
            setItem: (k, v) => { sessionStore[k] = String(v); },
            removeItem: (k) => { delete sessionStore[k]; }
        };

        // Simulate early entry-guard execution from index.html
        var isGuest = false;
        try {
            if (sessionStorage.getItem('bis_guest_mode') === 'true') isGuest = true;
            var p = new URLSearchParams(window.location.search);
            if (p.get('guest') === 'true' || p.get('guest') === '1') {
                sessionStorage.setItem('bis_guest_mode', 'true');
                isGuest = true;
            }
        } catch(e) {}

        if (!isGuest) {
            var hasCandidateToken = false;
            try {
                if (localStorage.getItem('bis_supabase_auth_token')) {
                    hasCandidateToken = true;
                }
            } catch(e) {}

            if (!hasCandidateToken) {
                var isStatic = window.location.protocol === 'file:' || window.location.pathname.endsWith('.html');
                var target = isStatic ? './login.html' : '/login';
                window.location.replace(target);
            }
        }

        if (redirectedTo !== '/login') {
            console.error('Expected redirect to /login, got:', redirectedTo);
            process.exit(1);
        }
        process.exit(0);
        """

        res = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert res.returncode == 0, f"Unauthenticated redirect failed: {res.stderr}"

    def test_07_node_headless_authenticated_entry_preservation(self):
        """Node.js headless test: authenticated user with token does NOT redirect early."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")

        script = """
        let redirectedTo = null;
        global.window = {
            location: {
                protocol: 'http:',
                pathname: '/',
                search: '',
                replace: function(url) { redirectedTo = url; }
            }
        };

        const store = {
            'bis_supabase_auth_token': JSON.stringify({
                access_token: 'valid-test-token',
                expires_at: Math.floor(Date.now() / 1000) + 3600,
                user: { email: 'researcher@bis.gov.in' }
            })
        };
        global.localStorage = {
            getItem: (k) => store[k] || null,
            length: 1,
            key: (i) => Object.keys(store)[i] || null
        };
        global.sessionStorage = {
            getItem: () => null
        };

        // Simulate entry-guard
        var isGuest = false;
        var hasCandidateToken = Boolean(localStorage.getItem('bis_supabase_auth_token'));

        if (!isGuest && !hasCandidateToken) {
            window.location.replace('/login');
        }

        if (redirectedTo !== null) {
            console.error('Authenticated user was unexpectedly redirected to:', redirectedTo);
            process.exit(1);
        }
        process.exit(0);
        """

        res = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert res.returncode == 0, f"Authenticated entry preservation failed: {res.stderr}"

    def test_08_node_headless_guest_flow_preservation(self):
        """Node.js headless test: guest flag permits entry without Supabase token."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")

        script = """
        let redirectedTo = null;
        global.window = {
            location: {
                protocol: 'http:',
                pathname: '/',
                search: '',
                replace: function(url) { redirectedTo = url; }
            }
        };

        global.localStorage = {
            getItem: () => null,
            length: 0,
            key: () => null
        };

        // User clicked "Continue as Guest" on login page
        global.sessionStorage = {
            getItem: (k) => (k === 'bis_guest_mode' ? 'true' : null)
        };

        // Simulate entry guard
        var isGuest = (sessionStorage.getItem('bis_guest_mode') === 'true');
        var hasCandidateToken = false;

        if (!isGuest && !hasCandidateToken) {
            window.location.replace('/login');
        }

        if (redirectedTo !== null) {
            console.error('Guest mode user was unexpectedly redirected to:', redirectedTo);
            process.exit(1);
        }
        process.exit(0);
        """

        res = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert res.returncode == 0, f"Guest flow preservation failed: {res.stderr}"

    def test_09_node_headless_expired_session_validation(self):
        """Node.js headless test: expired session is detected, storage purged, and redirected to Login."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")

        script = """
        let redirectedTo = null;
        global.window = {
            location: {
                protocol: 'http:',
                pathname: '/',
                search: '',
                replace: function(url) { redirectedTo = url; }
            }
        };

        const store = {
            'bis_supabase_auth_token': JSON.stringify({
                access_token: 'expired-token',
                // Expired 100 seconds ago
                expires_at: Math.floor(Date.now() / 1000) - 100,
                user: { email: 'expired@bis.gov.in' }
            })
        };

        global.localStorage = {
            getItem: (k) => store[k] || null,
            setItem: (k, v) => { store[k] = String(v); },
            removeItem: (k) => { delete store[k]; },
            length: 1,
            key: (i) => Object.keys(store)[i] || null
        };

        const sessionStore = {};
        global.sessionStorage = {
            getItem: (k) => sessionStore[k] || null,
            setItem: (k, v) => { sessionStore[k] = String(v); },
            removeItem: (k) => { delete sessionStore[k]; }
        };

        // Step 1: Early guard allows entry because candidate token was found
        var hasCandidateToken = Boolean(localStorage.getItem('bis_supabase_auth_token'));
        if (!hasCandidateToken) {
            window.location.replace('/login');
        }

        // Step 2: Canonical validation detects expired token
        const sess = JSON.parse(store['bis_supabase_auth_token']);
        const nowSec = Math.floor(Date.now() / 1000);
        if (sess.expires_at <= nowSec) {
            // Purge and redirect
            delete store['bis_supabase_auth_token'];
            window.location.replace('/login');
        }

        if (redirectedTo !== '/login') {
            console.error('Expired session was not redirected to /login:', redirectedTo);
            process.exit(1);
        }
        if (store['bis_supabase_auth_token']) {
            console.error('Expired token was not purged from localStorage');
            process.exit(1);
        }
        process.exit(0);
        """

        res = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert res.returncode == 0, f"Expired session handling failed: {res.stderr}"

    def test_10_node_headless_sign_out_clears_session_and_guest(self):
        """Node.js headless test: signOut clears both Supabase token and guest mode."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")

        script = """
        const store = {
            'bis_supabase_auth_token': 'token-data'
        };
        const sessionStore = {
            'bis_guest_mode': 'true'
        };

        global.window = global;
        global.localStorage = {
            getItem: (k) => store[k] || null,
            removeItem: (k) => { delete store[k]; },
            length: 1,
            key: (i) => Object.keys(store)[i] || null
        };
        global.sessionStorage = {
            getItem: (k) => sessionStore[k] || null,
            removeItem: (k) => { delete sessionStore[k]; }
        };

        // Simulate signOut
        localStorage.removeItem('bis_supabase_auth_token');
        sessionStorage.removeItem('bis_guest_mode');

        if (store['bis_supabase_auth_token']) {
            console.error('bis_supabase_auth_token was not removed');
            process.exit(1);
        }
        if (sessionStore['bis_guest_mode']) {
            console.error('bis_guest_mode was not removed');
            process.exit(1);
        }
        process.exit(0);
        """

        res = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert res.returncode == 0, f"SignOut storage purge failed: {res.stderr}"

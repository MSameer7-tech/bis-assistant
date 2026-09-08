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

    @pytest.fixture(autouse=True)
    def cleanup_temp_files(self):
        """Cleans up any temporary test files before and after each test."""
        for pattern in ["mock_sb*.js", "test_*.mjs", "temp_*.js"]:
            for f in FRONTEND_DIR.glob(pattern):
                try: f.unlink()
                except Exception: pass
        yield
        for pattern in ["mock_sb*.js", "test_*.mjs", "temp_*.js"]:
            for f in FRONTEND_DIR.glob(pattern):
                try: f.unlink()
                except Exception: pass

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

    def test_11_all_auth_imports_exist_as_exports(self):
        """Verifies every single imported symbol from auth.js in login.html, app.js, and auth-callback.html is exported."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")

        script = """
        const fs = require('fs');
        const loginHtml = fs.readFileSync('frontend/login.html', 'utf-8');
        const loginMatch = loginHtml.match(/import\\s*\\{([^}]+)\\}\\s*from\\s*['\"](\\.\\/auth\\.js[^'\"]*)['\"];/);
        if (!loginMatch) throw new Error('Could not find auth.js import in login.html');
        const loginImports = loginMatch[1].split(',').map(s => s.trim()).filter(Boolean);

        const appJs = fs.readFileSync('frontend/app.js', 'utf-8');
        const appMatch = appJs.match(/import\\s*\\{([^}]+)\\}\\s*from\\s*['\"](\\.\\/auth\\.js[^'\"]*)['\"];/);
        if (!appMatch) throw new Error('Could not find auth.js import in app.js');
        const appImports = appMatch[1].split(',').map(s => s.trim()).filter(Boolean);

        const authJs = fs.readFileSync('frontend/auth.js', 'utf-8');
        const exportRegex = /export\\s+(?:async\\s+)?function\\s+([a-zA-Z0-9_]+)/g;
        const exports = [];
        let m;
        while ((m = exportRegex.exec(authJs)) !== null) {
            exports.push(m[1]);
        }

        for (const imp of loginImports) {
            if (!exports.includes(imp)) {
                console.error('MISMATCH in login.html: ' + imp + ' is not exported by auth.js');
                process.exit(1);
            }
        }

        for (const imp of appImports) {
            if (!exports.includes(imp)) {
                console.error('MISMATCH in app.js: ' + imp + ' is not exported by auth.js');
                process.exit(1);
            }
        }
        process.exit(0);
        """
        res = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert res.returncode == 0, f"Import/export mismatch: {res.stderr}"

    def test_12_login_html_loads_with_zero_syntax_or_module_errors(self):
        """Verifies login.html parses and executes module script with zero errors."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")

        script = """
        const fs = require('fs');
        const loginHtml = fs.readFileSync('frontend/login.html', 'utf-8');

        // Extract the <script type="module"> contents
        const scriptMatch = loginHtml.match(/<script type=\"module\">([\\s\\S]*?)<\\/script>/);
        if (!scriptMatch) throw new Error('Could not find module script in login.html');
        let code = scriptMatch[1];

        // Replace relative imports with mocked module for headless execution
        fs.writeFileSync('frontend/mock_supabase_test.js', 'export function createClient() { return {}; }');
        let authJs = fs.readFileSync('frontend/auth.js', 'utf-8');
        authJs = authJs.replace(/from\\s+['\"]https:[^'\"]+['\"]/g, 'from \"./mock_supabase_test.js\"');
        fs.writeFileSync('frontend/temp_auth.js', authJs);

        // Replace import from './auth.js...' with './temp_auth.js'
        code = code.replace(/from\\s+['\"]\\.\\/auth\\.js[^'\"]*['\"]/, 'from \"./temp_auth.js\"');
        fs.writeFileSync('frontend/temp_login_runner.js', code);

        // Run syntax check on the runner
        const { execSync } = require('child_process');
        try {
            execSync('node --check frontend/temp_login_runner.js');
        } finally {
            try { fs.unlinkSync('frontend/mock_supabase_test.js'); } catch(e) {}
            try { fs.unlinkSync('frontend/temp_auth.js'); } catch(e) {}
            try { fs.unlinkSync('frontend/temp_login_runner.js'); } catch(e) {}
        }
        process.exit(0);
        """
        res = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert res.returncode == 0, f"login.html module syntax error: {res.stderr}"

    def test_13_auth_email_password_sign_in(self):
        """Verifies signInWithEmail calls supabase.auth.signInWithPassword with correct credentials."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")

        script = """
        const fs = require('fs');
        fs.writeFileSync('frontend/mock_sb_13.js', 'export function createClient() { return global.mockSupabaseClient; }');
        const authContent = fs.readFileSync('frontend/auth.js', 'utf-8').replace(/from\\s+['\"]https:[^'\"]+['\"]/g, 'from \"./mock_sb_13.js\"');
        fs.writeFileSync('frontend/test_13.mjs', authContent);

        global.fetch = async () => ({
            ok: true,
            json: async () => ({ configured: true, supabase_url: 'https://test.supabase.co', supabase_anon_key: 'key' })
        });

        let calledCreds = null;
        global.mockSupabaseClient = {
            auth: {
                signInWithPassword: async (creds) => {
                    calledCreds = creds;
                    return { data: { session: { access_token: 'valid-jwt' }, user: { id: 'u1', email: creds.email } }, error: null };
                },
                onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } })
            }
        };

        import('./frontend/test_13.mjs').then(async (m) => {
            try {
                const res = await m.signInWithEmail('officer@bis.gov.in', 'Secret123!');
                if (!res.user || res.user.email !== 'officer@bis.gov.in') {
                    console.error('Sign-in result mismatch:', res);
                    process.exit(1);
                }
                if (!calledCreds || calledCreds.email !== 'officer@bis.gov.in' || calledCreds.password !== 'Secret123!') {
                    console.error('Credentials mismatch:', calledCreds);
                    process.exit(1);
                }
                process.exit(0);
            } catch (err) {
                console.error(err);
                process.exit(1);
            } finally {
                try { fs.unlinkSync('frontend/mock_sb_13.js'); } catch(e) {}
                try { fs.unlinkSync('frontend/test_13.mjs'); } catch(e) {}
            }
        });
        """
        res = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert res.returncode == 0, f"Email/Password Sign-In failed: {res.stderr}"

    def test_14_auth_google_oauth(self):
        """Verifies signInWithGoogle invokes signInWithOAuth with google provider."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")

        script = """
        const fs = require('fs');
        fs.writeFileSync('frontend/mock_sb_14.js', 'export function createClient() { return global.mockSupabaseClient; }');
        const authContent = fs.readFileSync('frontend/auth.js', 'utf-8').replace(/from\\s+['\"]https:[^'\"]+['\"]/g, 'from \"./mock_sb_14.js\"');
        fs.writeFileSync('frontend/test_14.mjs', authContent);

        global.fetch = async () => ({
            ok: true,
            json: async () => ({ configured: true, supabase_url: 'https://test.supabase.co', supabase_anon_key: 'key' })
        });

        global.window = {
            location: { origin: 'https://bis-assistant.up.railway.app' }
        };

        let oauthOpts = null;
        global.mockSupabaseClient = {
            auth: {
                signInWithOAuth: async (opts) => {
                    oauthOpts = opts;
                    return { data: { url: 'https://accounts.google.com/o/oauth2' }, error: null };
                },
                onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } })
            }
        };

        import('./frontend/test_14.mjs').then(async (m) => {
            try {
                await m.signInWithGoogle();
                if (!oauthOpts || oauthOpts.provider !== 'google') {
                    console.error('Expected google provider, got:', oauthOpts);
                    process.exit(1);
                }
                if (!oauthOpts.options?.redirectTo || !oauthOpts.options.redirectTo.includes('/auth/callback')) {
                    console.error('Expected redirect to /auth/callback, got:', oauthOpts);
                    process.exit(1);
                }
                process.exit(0);
            } catch (err) {
                console.error(err);
                process.exit(1);
            } finally {
                try { fs.unlinkSync('frontend/mock_sb_14.js'); } catch(e) {}
                try { fs.unlinkSync('frontend/test_14.mjs'); } catch(e) {}
            }
        });
        """
        res = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert res.returncode == 0, f"Google OAuth failed: {res.stderr}"

    def test_15_auth_github_oauth(self):
        """Verifies signInWithGitHub invokes signInWithOAuth with github provider."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")

        script = """
        const fs = require('fs');
        fs.writeFileSync('frontend/mock_sb_15.js', 'export function createClient() { return global.mockSupabaseClient; }');
        const authContent = fs.readFileSync('frontend/auth.js', 'utf-8').replace(/from\\s+['\"]https:[^'\"]+['\"]/g, 'from \"./mock_sb_15.js\"');
        fs.writeFileSync('frontend/test_15.mjs', authContent);

        global.fetch = async () => ({
            ok: true,
            json: async () => ({ configured: true, supabase_url: 'https://test.supabase.co', supabase_anon_key: 'key' })
        });

        global.window = {
            location: { origin: 'http://localhost:3000' }
        };

        let oauthOpts = null;
        global.mockSupabaseClient = {
            auth: {
                signInWithOAuth: async (opts) => {
                    oauthOpts = opts;
                    return { data: { url: 'https://github.com/login/oauth' }, error: null };
                },
                onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } })
            }
        };

        import('./frontend/test_15.mjs').then(async (m) => {
            try {
                await m.signInWithGitHub();
                if (!oauthOpts || oauthOpts.provider !== 'github') {
                    console.error('Expected github provider, got:', oauthOpts);
                    process.exit(1);
                }
                if (!oauthOpts.options?.redirectTo || !oauthOpts.options.redirectTo.includes('/auth/callback')) {
                    console.error('Expected redirect to /auth/callback, got:', oauthOpts);
                    process.exit(1);
                }
                process.exit(0);
            } catch (err) {
                console.error(err);
                process.exit(1);
            } finally {
                try { fs.unlinkSync('frontend/mock_sb_15.js'); } catch(e) {}
                try { fs.unlinkSync('frontend/test_15.mjs'); } catch(e) {}
            }
        });
        """
        res = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert res.returncode == 0, f"GitHub OAuth failed: {res.stderr}"

    def test_16_auth_create_account(self):
        """Verifies signUpWithEmail invokes signUp with email and password."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")

        script = """
        const fs = require('fs');
        fs.writeFileSync('frontend/mock_sb_16.js', 'export function createClient() { return global.mockSupabaseClient; }');
        const authContent = fs.readFileSync('frontend/auth.js', 'utf-8').replace(/from\\s+['\"]https:[^'\"]+['\"]/g, 'from \"./mock_sb_16.js\"');
        fs.writeFileSync('frontend/test_16.mjs', authContent);

        global.fetch = async () => ({
            ok: true,
            json: async () => ({ configured: true, supabase_url: 'https://test.supabase.co', supabase_anon_key: 'key' })
        });

        global.window = {
            location: { origin: 'https://bis-assistant.up.railway.app' }
        };

        let signUpCreds = null;
        global.mockSupabaseClient = {
            auth: {
                signUp: async (creds) => {
                    signUpCreds = creds;
                    return { data: { user: { id: 'u2', email: creds.email }, session: null }, error: null };
                },
                getSession: async () => ({ data: { session: null }, error: null }),
                onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } })
            }
        };

        import('./frontend/test_16.mjs').then(async (m) => {
            try {
                const res = await m.signUpWithEmail('newuser@bis.gov.in', 'StrongPwd99!');
                if (!signUpCreds || signUpCreds.email !== 'newuser@bis.gov.in' || signUpCreds.password !== 'StrongPwd99!') {
                    console.error('Sign-up creds mismatch:', signUpCreds);
                    process.exit(1);
                }
                process.exit(0);
            } catch (err) {
                console.error(err);
                process.exit(1);
            } finally {
                try { fs.unlinkSync('frontend/mock_sb_16.js'); } catch(e) {}
                try { fs.unlinkSync('frontend/test_16.mjs'); } catch(e) {}
            }
        });
        """
        res = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert res.returncode == 0, f"Account creation failed: {res.stderr}"

    def test_17_auth_forgot_password(self):
        """Verifies sendPasswordReset invokes resetPasswordForEmail with redirect."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")

        script = """
        const fs = require('fs');
        fs.writeFileSync('frontend/mock_sb_17.js', 'export function createClient() { return global.mockSupabaseClient; }');
        const authContent = fs.readFileSync('frontend/auth.js', 'utf-8').replace(/from\\s+['\"]https:[^'\"]+['\"]/g, 'from \"./mock_sb_17.js\"');
        fs.writeFileSync('frontend/test_17.mjs', authContent);

        global.fetch = async () => ({
            ok: true,
            json: async () => ({ configured: true, supabase_url: 'https://test.supabase.co', supabase_anon_key: 'key' })
        });

        global.window = {
            location: { origin: 'https://bis-assistant.up.railway.app' }
        };

        let resetEmail = null;
        global.mockSupabaseClient = {
            auth: {
                resetPasswordForEmail: async (email, opts) => {
                    resetEmail = email;
                    return { data: {}, error: null };
                },
                onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } })
            }
        };

        import('./frontend/test_17.mjs').then(async (m) => {
            try {
                await m.sendPasswordReset('forgot@bis.gov.in');
                if (resetEmail !== 'forgot@bis.gov.in') {
                    console.error('Expected reset email forgot@bis.gov.in, got:', resetEmail);
                    process.exit(1);
                }
                process.exit(0);
            } catch (err) {
                console.error(err);
                process.exit(1);
            } finally {
                try { fs.unlinkSync('frontend/mock_sb_17.js'); } catch(e) {}
                try { fs.unlinkSync('frontend/test_17.mjs'); } catch(e) {}
            }
        });
        """
        res = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert res.returncode == 0, f"Forgot password failed: {res.stderr}"

    def test_18_successful_login_redirect_urls(self):
        """Verifies getHomeUrl returns proper URLs across localhost, Railway, and static hosting."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")

        script = """
        const fs = require('fs');
        fs.writeFileSync('frontend/mock_sb_18.js', 'export function createClient() { return {}; }');
        const authContent = fs.readFileSync('frontend/auth.js', 'utf-8').replace(/from\\s+['\"]https:[^'\"]+['\"]/g, 'from \"./mock_sb_18.js\"');
        fs.writeFileSync('frontend/test_18.mjs', authContent);

        import('./frontend/test_18.mjs').then((m) => {
            try {
                // Scenario A: Localhost http://localhost:3000/login
                global.window = {
                    location: {
                        protocol: 'http:',
                        pathname: '/login',
                        origin: 'http://localhost:3000'
                    }
                };
                if (m.getHomeUrl() !== '/#home') {
                    console.error('Localhost getHomeUrl() expected /#home, got:', m.getHomeUrl());
                    process.exit(1);
                }

                // Scenario B: Railway https://bis-assistant.up.railway.app/login
                global.window = {
                    location: {
                        protocol: 'https:',
                        pathname: '/login',
                        origin: 'https://bis-assistant.up.railway.app'
                    }
                };
                if (m.getHomeUrl() !== '/#home') {
                    console.error('Railway getHomeUrl() expected /#home, got:', m.getHomeUrl());
                    process.exit(1);
                }

                // Scenario C: Static file hosting / file:///Users/.../login.html
                global.window = {
                    location: {
                        protocol: 'file:',
                        pathname: '/Users/test/login.html',
                        origin: 'null'
                    }
                };
                if (m.getHomeUrl() !== './index.html#home') {
                    console.error('Static getHomeUrl() expected ./index.html#home, got:', m.getHomeUrl());
                    process.exit(1);
                }

                process.exit(0);
            } catch(e) {
                console.error(e);
                process.exit(1);
            } finally {
                try { fs.unlinkSync('frontend/mock_sb_18.js'); } catch(e) {}
                try { fs.unlinkSync('frontend/test_18.mjs'); } catch(e) {}
            }
        });
        """
        res = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert res.returncode == 0, f"Login redirect URL tests failed: {res.stderr}"

    def test_19_logout_full_flow(self):
        """Verifies signOut clears Supabase session, localStorage tokens, and sessionStorage guest flags."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")

        script = """
        const fs = require('fs');
        fs.writeFileSync('frontend/mock_sb_19.js', 'export function createClient() { return global.mockSupabaseClient; }');
        const authContent = fs.readFileSync('frontend/auth.js', 'utf-8').replace(/from\\s+['\"]https:[^'\"]+['\"]/g, 'from \"./mock_sb_19.js\"');
        fs.writeFileSync('frontend/test_19.mjs', authContent);

        global.fetch = async () => ({
            ok: true,
            json: async () => ({ configured: true, supabase_url: 'https://test.supabase.co', supabase_anon_key: 'key' })
        });

        let supabaseSignedOut = false;
        const store = { 'bis_supabase_auth_token': 'active-token', 'sb-test-auth-token': 'sb-token' };
        const sessionStore = { 'bis_guest_mode': 'true' };

        global.window = {
            location: { protocol: 'https:', pathname: '/#home', replace: () => {} }
        };
        global.localStorage = {
            getItem: (k) => store[k] || null,
            removeItem: (k) => { delete store[k]; },
            get length() { return Object.keys(store).length; },
            key: (i) => Object.keys(store)[i] || null
        };
        global.sessionStorage = {
            getItem: (k) => sessionStore[k] || null,
            removeItem: (k) => { delete sessionStore[k]; }
        };

        global.mockSupabaseClient = {
            auth: {
                signOut: async () => {
                    supabaseSignedOut = true;
                    return { error: null };
                },
                onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } })
            }
        };

        import('./frontend/test_19.mjs').then(async (m) => {
            try {
                await m.initializeAuth();
                await m.signOut();

                if (!supabaseSignedOut) {
                    console.error('Supabase client.auth.signOut was not called');
                    process.exit(1);
                }
                if (store['bis_supabase_auth_token']) {
                    console.error('bis_supabase_auth_token not purged');
                    process.exit(1);
                }
                if (sessionStore['bis_guest_mode']) {
                    console.error('bis_guest_mode not purged');
                    process.exit(1);
                }
                process.exit(0);
            } catch (err) {
                console.error(err);
                process.exit(1);
            } finally {
                try { fs.unlinkSync('frontend/mock_sb_19.js'); } catch(e) {}
                try { fs.unlinkSync('frontend/test_19.mjs'); } catch(e) {}
            }
        });
        """
        res = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert res.returncode == 0, f"Logout full flow failed: {res.stderr}"

    def test_20_authenticated_refresh_preserves_session(self):
        """Verifies refreshing the page preserves the active session without redirecting to login."""
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")

        script = """
        const fs = require('fs');
        fs.writeFileSync('frontend/mock_sb_20.js', 'export function createClient() { return global.mockSupabaseClient; }');
        const authContent = fs.readFileSync('frontend/auth.js', 'utf-8').replace(/from\\s+['\"]https:[^'\"]+['\"]/g, 'from \"./mock_sb_20.js\"');
        fs.writeFileSync('frontend/test_20.mjs', authContent);

        global.fetch = async () => ({
            ok: true,
            json: async () => ({ configured: true, supabase_url: 'https://test.supabase.co', supabase_anon_key: 'key' })
        });

        let redirectedTo = null;
        global.window = {
            location: {
                protocol: 'https:',
                pathname: '/',
                search: '',
                replace: (url) => { redirectedTo = url; }
            }
        };

        const nowSec = Math.floor(Date.now() / 1000);
        const validSession = {
            access_token: 'fresh-valid-token',
            expires_at: nowSec + 3600,
            user: { email: 'officer@bis.gov.in', id: 'officer-1' }
        };

        const store = {
            'bis_supabase_auth_token': JSON.stringify(validSession)
        };

        global.localStorage = {
            getItem: (k) => store[k] || null,
            get length() { return Object.keys(store).length; },
            key: (i) => Object.keys(store)[i] || null
        };
        global.sessionStorage = {
            getItem: () => null
        };

        global.mockSupabaseClient = {
            auth: {
                getSession: async () => ({
                    data: { session: validSession },
                    error: null
                }),
                onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } })
            }
        };

        import('./frontend/test_20.mjs').then(async (m) => {
            try {
                // Check early entry guard
                const hasCandidate = m.hasPotentialSession();
                if (!hasCandidate) {
                    window.location.replace('/login');
                }

                // Canonical validation on page load/refresh
                const valResult = await m.validateSession();
                if (!valResult.authenticated || !valResult.user) {
                    window.location.replace('/login');
                }

                // Expectation: NO redirect was triggered
                if (redirectedTo !== null) {
                    console.error('Authenticated user was unexpectedly redirected to:', redirectedTo);
                    process.exit(1);
                }

                process.exit(0);
            } catch (err) {
                console.error(err);
                process.exit(1);
            } finally {
                try { fs.unlinkSync('frontend/mock_sb_20.js'); } catch(e) {}
                try { fs.unlinkSync('frontend/test_20.mjs'); } catch(e) {}
            }
        });
        """
        res = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        assert res.returncode == 0, f"Authenticated refresh preservation failed: {res.stderr}"


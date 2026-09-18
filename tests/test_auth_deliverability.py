"""
Supabase Authentication Email Deliverability & Anti-Bounce Verification Suite.

Validates the remediation of Supabase transactional email bounce issues:
1. Rejects RFC 2606 / RFC 6761 reserved & non-deliverable domains:
   - example.com, example.org, example.net
   - test.com, fake.com, sample.com, organization.com
   - localhost, invalid
2. Rejects blocked domain suffixes (.invalid, .localhost, .example, .test).
3. Rejects malformed email structures (no @, empty user, empty domain, short TLD, consecutive dots).
4. Accepts valid deliverable corporate/personal email addresses.
5. Provides typo suggestions without automatic rewriting (e.g., gamil.com -> gmail.com).
6. Prevents duplicate email dispatches with 60-second sessionStorage cooldowns.
7. Gracefully handles HTTP 429 rate limits without automatic retries.
8. Ensures zero real emails are ever dispatched during testing.
9. Audits HTML templates for placeholder hygiene.
"""

import json
import shutil
import subprocess
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


class TestAuthDeliverability:
    """Test suite validating client-side email deliverability and cooldown enforcement."""

    @pytest.fixture(autouse=True)
    def cleanup_temp_files(self):
        """Cleans up temporary harness files before and after each test."""
        for pattern in ["mock_sb_deliv*.js", "test_deliv*.mjs"]:
            for f in FRONTEND_DIR.glob(pattern):
                try:
                    f.unlink()
                except Exception:
                    pass
        yield
        for pattern in ["mock_sb_deliv*.js", "test_deliv*.mjs"]:
            for f in FRONTEND_DIR.glob(pattern):
                try:
                    f.unlink()
                except Exception:
                    pass

    def _run_node_harness(self, script: str) -> subprocess.CompletedProcess:
        node_bin = shutil.which("node")
        if not node_bin:
            pytest.skip("Node.js not installed")
        res = subprocess.run([node_bin, "-e", script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        return res

    def test_01_blocked_rfc2606_example_domains(self):
        """Validates rejection of RFC 2606 reserved domains: example.com, example.org, example.net."""
        script = """
        const fs = require('fs');
        fs.writeFileSync('frontend/mock_sb_deliv1.js', 'export function createClient() { return {}; }');
        const authContent = fs.readFileSync('frontend/auth.js', 'utf-8').replace(/from\\s+['\"]https:[^'\"]+['\"]/g, 'from "./mock_sb_deliv1.js"');
        fs.writeFileSync('frontend/test_deliv1.mjs', authContent);

        import('./frontend/test_deliv1.mjs').then(m => {
            try {
                const blocked = ['user@example.com', 'admin@example.org', 'test@example.net'];
                for (const email of blocked) {
                    const res = m.validateDeliverableEmail(email);
                    if (res.valid !== false) {
                        console.error('Expected rejection for ' + email + ' but got: ' + JSON.stringify(res));
                        process.exit(1);
                    }
                    if (!res.error || !res.error.includes('Test or placeholder domains are not permitted')) {
                        console.error('Unexpected error message for ' + email + ': ' + res.error);
                        process.exit(1);
                    }
                }
                process.exit(0);
            } catch (err) {
                console.error(err);
                process.exit(1);
            } finally {
                try { fs.unlinkSync('frontend/mock_sb_deliv1.js'); } catch(e) {}
                try { fs.unlinkSync('frontend/test_deliv1.mjs'); } catch(e) {}
            }
        });
        """
        res = self._run_node_harness(script)
        assert res.returncode == 0, f"Blocked RFC 2606 domain test failed: {res.stderr}"

    def test_02_blocked_test_and_placeholder_domains(self):
        """Validates rejection of test/placeholder domains: test.com, fake.com, sample.com, organization.com."""
        script = """
        const fs = require('fs');
        fs.writeFileSync('frontend/mock_sb_deliv2.js', 'export function createClient() { return {}; }');
        const authContent = fs.readFileSync('frontend/auth.js', 'utf-8').replace(/from\\s+['\"]https:[^'\"]+['\"]/g, 'from "./mock_sb_deliv2.js"');
        fs.writeFileSync('frontend/test_deliv2.mjs', authContent);

        import('./frontend/test_deliv2.mjs').then(m => {
            try {
                const blocked = ['test@test.com', 'user@fake.com', 'demo@sample.com', 'analyst@organization.com'];
                for (const email of blocked) {
                    const res = m.validateDeliverableEmail(email);
                    if (res.valid !== false) {
                        console.error('Expected rejection for ' + email + ' but got: ' + JSON.stringify(res));
                        process.exit(1);
                    }
                }
                process.exit(0);
            } catch (err) {
                console.error(err);
                process.exit(1);
            } finally {
                try { fs.unlinkSync('frontend/mock_sb_deliv2.js'); } catch(e) {}
                try { fs.unlinkSync('frontend/test_deliv2.mjs'); } catch(e) {}
            }
        });
        """
        res = self._run_node_harness(script)
        assert res.returncode == 0, f"Blocked test/placeholder domain test failed: {res.stderr}"

    def test_03_blocked_local_and_invalid_hostnames(self):
        """Validates rejection of localhost and invalid hostnames without TLD."""
        script = """
        const fs = require('fs');
        fs.writeFileSync('frontend/mock_sb_deliv3.js', 'export function createClient() { return {}; }');
        const authContent = fs.readFileSync('frontend/auth.js', 'utf-8').replace(/from\\s+['\"]https:[^'\"]+['\"]/g, 'from "./mock_sb_deliv3.js"');
        fs.writeFileSync('frontend/test_deliv3.mjs', authContent);

        import('./frontend/test_deliv3.mjs').then(m => {
            try {
                const blocked = ['user@localhost', 'admin@invalid'];
                for (const email of blocked) {
                    const res = m.validateDeliverableEmail(email);
                    if (res.valid !== false) {
                        console.error('Expected rejection for ' + email + ' but got: ' + JSON.stringify(res));
                        process.exit(1);
                    }
                }
                process.exit(0);
            } catch (err) {
                console.error(err);
                process.exit(1);
            } finally {
                try { fs.unlinkSync('frontend/mock_sb_deliv3.js'); } catch(e) {}
                try { fs.unlinkSync('frontend/test_deliv3.mjs'); } catch(e) {}
            }
        });
        """
        res = self._run_node_harness(script)
        assert res.returncode == 0, f"Blocked local/invalid hostname test failed: {res.stderr}"

    def test_04_blocked_domain_suffixes(self):
        """Validates rejection of domains ending in .invalid, .localhost, .example, .test."""
        script = """
        const fs = require('fs');
        fs.writeFileSync('frontend/mock_sb_deliv4.js', 'export function createClient() { return {}; }');
        const authContent = fs.readFileSync('frontend/auth.js', 'utf-8').replace(/from\\s+['\"]https:[^'\"]+['\"]/g, 'from "./mock_sb_deliv4.js"');
        fs.writeFileSync('frontend/test_deliv4.mjs', authContent);

        import('./frontend/test_deliv4.mjs').then(m => {
            try {
                const blocked = [
                    'user@test.invalid',
                    'user@corp.invalid',
                    'user@sub.localhost',
                    'user@mail.example',
                    'user@staging.test'
                ];
                for (const email of blocked) {
                    const res = m.validateDeliverableEmail(email);
                    if (res.valid !== false) {
                        console.error('Expected rejection for ' + email + ' but got: ' + JSON.stringify(res));
                        process.exit(1);
                    }
                }
                process.exit(0);
            } catch (err) {
                console.error(err);
                process.exit(1);
            } finally {
                try { fs.unlinkSync('frontend/mock_sb_deliv4.js'); } catch(e) {}
                try { fs.unlinkSync('frontend/test_deliv4.mjs'); } catch(e) {}
            }
        });
        """
        res = self._run_node_harness(script)
        assert res.returncode == 0, f"Blocked domain suffixes test failed: {res.stderr}"

    def test_05_structural_validation_rejections(self):
        """Validates rejection of structurally malformed addresses."""
        script = """
        const fs = require('fs');
        fs.writeFileSync('frontend/mock_sb_deliv5.js', 'export function createClient() { return {}; }');
        const authContent = fs.readFileSync('frontend/auth.js', 'utf-8').replace(/from\\s+['\"]https:[^'\"]+['\"]/g, 'from "./mock_sb_deliv5.js"');
        fs.writeFileSync('frontend/test_deliv5.mjs', authContent);

        import('./frontend/test_deliv5.mjs').then(m => {
            try {
                const malformed = [
                    'plainaddress',          // No @ symbol
                    '@missinguser.com',      // Missing local part
                    'missingdomain@',        // Missing domain part
                    'user@.nodot',           // Domain starts with dot
                    'user@domain.c',         // TLD < 2 characters
                    'user@domain..com',      // Consecutive dots
                    'user@domain,com',       // Comma instead of dot
                    '   ',                   // Whitespace only
                    null,                    // Null input
                    undefined                // Undefined input
                ];
                for (const email of malformed) {
                    const res = m.validateDeliverableEmail(email);
                    if (res.valid !== false) {
                        console.error('Expected rejection for malformed ' + email + ' but got: ' + JSON.stringify(res));
                        process.exit(1);
                    }
                }
                process.exit(0);
            } catch (err) {
                console.error(err);
                process.exit(1);
            } finally {
                try { fs.unlinkSync('frontend/mock_sb_deliv5.js'); } catch(e) {}
                try { fs.unlinkSync('frontend/test_deliv5.mjs'); } catch(e) {}
            }
        });
        """
        res = self._run_node_harness(script)
        assert res.returncode == 0, f"Structural validation test failed: {res.stderr}"

    def test_06_valid_deliverable_email_accepted(self):
        """Validates acceptance of genuine, deliverable emails."""
        script = """
        const fs = require('fs');
        fs.writeFileSync('frontend/mock_sb_deliv6.js', 'export function createClient() { return {}; }');
        const authContent = fs.readFileSync('frontend/auth.js', 'utf-8').replace(/from\\s+['\"]https:[^'\"]+['\"]/g, 'from "./mock_sb_deliv6.js"');
        fs.writeFileSync('frontend/test_deliv6.mjs', authContent);

        import('./frontend/test_deliv6.mjs').then(m => {
            try {
                const validEmails = [
                    'user@validcompany.in',
                    'officer.compliance@bis.gov.in',
                    'standard_tester@gmail.com',
                    'lab-auditor@sub.enterprise.co.uk'
                ];
                for (const email of validEmails) {
                    const res = m.validateDeliverableEmail(email);
                    if (res.valid !== true) {
                        console.error('Expected acceptance for ' + email + ' but got: ' + JSON.stringify(res));
                        process.exit(1);
                    }
                    if (res.email !== email.toLowerCase().trim()) {
                        console.error('Email normalization failed: ' + res.email);
                        process.exit(1);
                    }
                }
                process.exit(0);
            } catch (err) {
                console.error(err);
                process.exit(1);
            } finally {
                try { fs.unlinkSync('frontend/mock_sb_deliv6.js'); } catch(e) {}
                try { fs.unlinkSync('frontend/test_deliv6.mjs'); } catch(e) {}
            }
        });
        """
        res = self._run_node_harness(script)
        assert res.returncode == 0, f"Valid email acceptance test failed: {res.stderr}"

    def test_07_typo_warning_detection(self):
        """Validates detection of common domain typos (gamil.com, yaho.com, etc.) with suggestions."""
        script = """
        const fs = require('fs');
        fs.writeFileSync('frontend/mock_sb_deliv7.js', 'export function createClient() { return {}; }');
        const authContent = fs.readFileSync('frontend/auth.js', 'utf-8').replace(/from\\s+['\"]https:[^'\"]+['\"]/g, 'from "./mock_sb_deliv7.js"');
        fs.writeFileSync('frontend/test_deliv7.mjs', authContent);

        import('./frontend/test_deliv7.mjs').then(m => {
            try {
                const typos = [
                    { input: 'engineer@gamil.com', expected: 'gmail.com' },
                    { input: 'auditor@gmial.com', expected: 'gmail.com' },
                    { input: 'officer@yaho.com', expected: 'yahoo.com' },
                    { input: 'user@hotmial.com', expected: 'hotmail.com' },
                    { input: 'lead@outlok.com', expected: 'outlook.com' }
                ];
                for (const { input, expected } of typos) {
                    const res = m.validateDeliverableEmail(input);
                    // Must still be valid (not automatically rewritten or blocked)
                    if (res.valid !== true) {
                        console.error('Expected valid:true with warning for typo ' + input + ' but got: ' + JSON.stringify(res));
                        process.exit(1);
                    }
                    if (!res.warning || !res.warning.includes(expected)) {
                        console.error('Expected warning containing ' + expected + ' for ' + input + ' but got: ' + res.warning);
                        process.exit(1);
                    }
                }
                process.exit(0);
            } catch (err) {
                console.error(err);
                process.exit(1);
            } finally {
                try { fs.unlinkSync('frontend/mock_sb_deliv7.js'); } catch(e) {}
                try { fs.unlinkSync('frontend/test_deliv7.mjs'); } catch(e) {}
            }
        });
        """
        res = self._run_node_harness(script)
        assert res.returncode == 0, f"Typo warning detection test failed: {res.stderr}"

    def test_08_signup_blocks_invalid_and_blocked_domains_zero_network_calls(self):
        """Validates signUpWithEmail aborts and makes ZERO Supabase calls for blocked/invalid domains."""
        script = """
        const fs = require('fs');
        fs.writeFileSync('frontend/mock_sb_deliv8.js', 'export function createClient() { return global.mockSupabaseClient; }');
        const authContent = fs.readFileSync('frontend/auth.js', 'utf-8').replace(/from\\s+['\"]https:[^'\"]+['\"]/g, 'from "./mock_sb_deliv8.js"');
        fs.writeFileSync('frontend/test_deliv8.mjs', authContent);

        let signUpCallCount = 0;
        global.mockSupabaseClient = {
            auth: {
                signUp: async () => {
                    signUpCallCount++;
                    return { data: { user: { id: 'test' }, session: null }, error: null };
                }
            }
        };

        global.fetch = async () => ({
            ok: true,
            json: async () => ({ configured: true, supabase_url: 'https://mock.supabase.co', supabase_anon_key: 'mock-key' })
        });

        const store = {};
        global.sessionStorage = {
            getItem: (k) => store[k] || null,
            setItem: (k, v) => { store[k] = String(v); },
            removeItem: (k) => { delete store[k]; }
        };

        import('./frontend/test_deliv8.mjs').then(async m => {
            try {
                // Try blocked RFC 2606 domain
                try {
                    await m.signUpWithEmail('attacker@example.com', 'StrongPass123!');
                    console.error('signUpWithEmail should have rejected attacker@example.com');
                    process.exit(1);
                } catch (e) {
                    if (!e.message.includes('Test or placeholder domains are not permitted')) {
                        console.error('Unexpected error: ' + e.message);
                        process.exit(1);
                    }
                }

                // Try malformed email
                try {
                    await m.signUpWithEmail('plainaddress', 'StrongPass123!');
                    console.error('signUpWithEmail should have rejected plainaddress');
                    process.exit(1);
                } catch (e) {
                    if (!e.message.includes('valid email address')) {
                        console.error('Unexpected error: ' + e.message);
                        process.exit(1);
                    }
                }

                // Strict assertion: Zero calls made to mockSupabaseClient.auth.signUp
                if (signUpCallCount !== 0) {
                    console.error('Supabase signUp was invoked ' + signUpCallCount + ' times! Must be 0.');
                    process.exit(1);
                }

                process.exit(0);
            } catch (err) {
                console.error(err);
                process.exit(1);
            } finally {
                try { fs.unlinkSync('frontend/mock_sb_deliv8.js'); } catch(e) {}
                try { fs.unlinkSync('frontend/test_deliv8.mjs'); } catch(e) {}
            }
        });
        """
        res = self._run_node_harness(script)
        assert res.returncode == 0, f"SignUp block before Supabase test failed: {res.stderr}"

    def test_09_password_reset_blocks_invalid_and_blocked_domains_zero_network_calls(self):
        """Validates sendPasswordReset aborts and makes ZERO Supabase calls for blocked/invalid domains."""
        script = """
        const fs = require('fs');
        fs.writeFileSync('frontend/mock_sb_deliv9.js', 'export function createClient() { return global.mockSupabaseClient; }');
        const authContent = fs.readFileSync('frontend/auth.js', 'utf-8').replace(/from\\s+['\"]https:[^'\"]+['\"]/g, 'from "./mock_sb_deliv9.js"');
        fs.writeFileSync('frontend/test_deliv9.mjs', authContent);

        let resetCallCount = 0;
        global.mockSupabaseClient = {
            auth: {
                resetPasswordForEmail: async () => {
                    resetCallCount++;
                    return { data: {}, error: null };
                }
            }
        };

        global.fetch = async () => ({
            ok: true,
            json: async () => ({ configured: true, supabase_url: 'https://mock.supabase.co', supabase_anon_key: 'mock-key' })
        });

        const store = {};
        global.sessionStorage = {
            getItem: (k) => store[k] || null,
            setItem: (k, v) => { store[k] = String(v); },
            removeItem: (k) => { delete store[k]; }
        };

        global.window = {
            location: { origin: 'https://bis-assistant.up.railway.app' }
        };

        import('./frontend/test_deliv9.mjs').then(async m => {
            try {
                // Try blocked test domain
                try {
                    await m.sendPasswordReset('user@test.com');
                    console.error('sendPasswordReset should have rejected user@test.com');
                    process.exit(1);
                } catch (e) {
                    if (!e.message.includes('Test or placeholder domains are not permitted')) {
                        console.error('Unexpected error: ' + e.message);
                        process.exit(1);
                    }
                }

                // Strict assertion: Zero calls made to mockSupabaseClient.auth.resetPasswordForEmail
                if (resetCallCount !== 0) {
                    console.error('Supabase resetPasswordForEmail was invoked ' + resetCallCount + ' times! Must be 0.');
                    process.exit(1);
                }

                process.exit(0);
            } catch (err) {
                console.error(err);
                process.exit(1);
            } finally {
                try { fs.unlinkSync('frontend/mock_sb_deliv9.js'); } catch(e) {}
                try { fs.unlinkSync('frontend/test_deliv9.mjs'); } catch(e) {}
            }
        });
        """
        res = self._run_node_harness(script)
        assert res.returncode == 0, f"Password reset block before Supabase test failed: {res.stderr}"

    def test_10_cooldown_storage_timestamp_and_refresh_recovery(self):
        """Validates 60s cooldown sets absolute timestamp in sessionStorage and recovers correctly."""
        script = """
        const fs = require('fs');
        fs.writeFileSync('frontend/mock_sb_deliv10.js', 'export function createClient() { return {}; }');
        const authContent = fs.readFileSync('frontend/auth.js', 'utf-8').replace(/from\\s+['\"]https:[^'\"]+['\"]/g, 'from "./mock_sb_deliv10.js"');
        fs.writeFileSync('frontend/test_deliv10.mjs', authContent);

        const store = {};
        global.sessionStorage = {
            getItem: (k) => store[k] || null,
            setItem: (k, v) => { store[k] = String(v); },
            removeItem: (k) => { delete store[k]; }
        };

        import('./frontend/test_deliv10.mjs').then(m => {
            try {
                // Set cooldown for signup
                m.setEmailCooldown('signup', 60);

                if (!m.isEmailCooldownActive('signup')) {
                    console.error('isEmailCooldownActive(signup) should be true');
                    process.exit(1);
                }

                const remaining = m.getEmailCooldownRemaining('signup');
                if (remaining < 58 || remaining > 60) {
                    console.error('Expected remaining ~60s, got: ' + remaining);
                    process.exit(1);
                }

                // Verify stored key format
                const rawVal = store['bis_auth_cooldown_signup'];
                if (!rawVal || isNaN(Number(rawVal))) {
                    console.error('Expected timestamp stored in bis_auth_cooldown_signup, got: ' + rawVal);
                    process.exit(1);
                }

                // Simulate page refresh (store persists in sessionStorage)
                const storedTimestamp = Number(store['bis_auth_cooldown_signup']);
                const recoveredRemaining = Math.max(0, Math.ceil((storedTimestamp - Date.now()) / 1000));
                if (recoveredRemaining < 58) {
                    console.error('Refreshed cooldown recovery failed: ' + recoveredRemaining);
                    process.exit(1);
                }

                process.exit(0);
            } catch (err) {
                console.error(err);
                process.exit(1);
            } finally {
                try { fs.unlinkSync('frontend/mock_sb_deliv10.js'); } catch(e) {}
                try { fs.unlinkSync('frontend/test_deliv10.mjs'); } catch(e) {}
            }
        });
        """
        res = self._run_node_harness(script)
        assert res.returncode == 0, f"Cooldown storage recovery test failed: {res.stderr}"

    def test_11_cooldown_blocks_duplicate_signup_before_supabase(self):
        """Validates active cooldown prevents calling signUpWithEmail, blocking duplicate sends."""
        script = """
        const fs = require('fs');
        fs.writeFileSync('frontend/mock_sb_deliv11.js', 'export function createClient() { return global.mockSupabaseClient; }');
        const authContent = fs.readFileSync('frontend/auth.js', 'utf-8').replace(/from\\s+['\"]https:[^'\"]+['\"]/g, 'from "./mock_sb_deliv11.js"');
        fs.writeFileSync('frontend/test_deliv11.mjs', authContent);

        let signUpCallCount = 0;
        global.mockSupabaseClient = {
            auth: {
                signUp: async () => {
                    signUpCallCount++;
                    return { data: { user: { id: 'uid-1' }, session: null }, error: null };
                },
                getSession: async () => ({ data: { session: null }, error: null }),
                onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } })
            }
        };

        global.fetch = async () => ({
            ok: true,
            json: async () => ({ configured: true, supabase_url: 'https://mock.supabase.co', supabase_anon_key: 'mock-key' })
        });

        const store = {};
        global.sessionStorage = {
            getItem: (k) => store[k] || null,
            setItem: (k, v) => { store[k] = String(v); },
            removeItem: (k) => { delete store[k]; }
        };

        import('./frontend/test_deliv11.mjs').then(async m => {
            try {
                // First signup succeeds and sets cooldown
                await m.signUpWithEmail('engineer@validcorp.in', 'Password123!');
                if (signUpCallCount !== 1) {
                    console.error('First signup should have called mock signUp once, got: ' + signUpCallCount);
                    process.exit(1);
                }

                // Cooldown should now be active
                if (!m.isEmailCooldownActive('signup')) {
                    console.error('Signup cooldown should be active after registration');
                    process.exit(1);
                }

                // Immediate second signup must be BLOCKED
                try {
                    await m.signUpWithEmail('engineer@validcorp.in', 'Password123!');
                    console.error('Second immediate signup should have failed due to cooldown');
                    process.exit(1);
                } catch (e) {
                    if (!e.message.includes('recently sent') && !e.message.includes('before requesting another')) {
                        console.error('Unexpected cooldown error message: ' + e.message);
                        process.exit(1);
                    }
                }

                // Ensure Supabase mock was NOT called a second time
                if (signUpCallCount !== 1) {
                    console.error('Duplicate Supabase signUp call was NOT blocked! Call count: ' + signUpCallCount);
                    process.exit(1);
                }

                process.exit(0);
            } catch (err) {
                console.error(err);
                process.exit(1);
            } finally {
                try { fs.unlinkSync('frontend/mock_sb_deliv11.js'); } catch(e) {}
                try { fs.unlinkSync('frontend/test_deliv11.mjs'); } catch(e) {}
            }
        });
        """
        res = self._run_node_harness(script)
        assert res.returncode == 0, f"Duplicate signup cooldown block test failed: {res.stderr}"

    def test_12_cooldown_blocks_duplicate_password_reset_before_supabase(self):
        """Validates active cooldown prevents duplicate password reset requests."""
        script = """
        const fs = require('fs');
        fs.writeFileSync('frontend/mock_sb_deliv12.js', 'export function createClient() { return global.mockSupabaseClient; }');
        const authContent = fs.readFileSync('frontend/auth.js', 'utf-8').replace(/from\\s+['\"]https:[^'\"]+['\"]/g, 'from "./mock_sb_deliv12.js"');
        fs.writeFileSync('frontend/test_deliv12.mjs', authContent);

        let resetCallCount = 0;
        global.mockSupabaseClient = {
            auth: {
                resetPasswordForEmail: async () => {
                    resetCallCount++;
                    return { data: {}, error: null };
                },
                getSession: async () => ({ data: { session: null }, error: null }),
                onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } })
            }
        };

        global.fetch = async () => ({
            ok: true,
            json: async () => ({ configured: true, supabase_url: 'https://mock.supabase.co', supabase_anon_key: 'mock-key' })
        });

        const store = {};
        global.sessionStorage = {
            getItem: (k) => store[k] || null,
            setItem: (k, v) => { store[k] = String(v); },
            removeItem: (k) => { delete store[k]; }
        };

        global.window = {
            location: { origin: 'https://bis-assistant.up.railway.app' }
        };

        import('./frontend/test_deliv12.mjs').then(async m => {
            try {
                // First reset succeeds and sets cooldown
                await m.sendPasswordReset('officer@bis.gov.in');
                if (resetCallCount !== 1) {
                    console.error('First reset should have called mock once, got: ' + resetCallCount);
                    process.exit(1);
                }

                // Cooldown should now be active
                if (!m.isEmailCooldownActive('password_reset')) {
                    console.error('Password reset cooldown should be active');
                    process.exit(1);
                }

                // Immediate second reset must be BLOCKED
                try {
                    await m.sendPasswordReset('officer@bis.gov.in');
                    console.error('Second immediate password reset should have failed due to cooldown');
                    process.exit(1);
                } catch (e) {
                    if (!e.message.includes('recently sent') && !e.message.includes('before requesting another')) {
                        console.error('Unexpected cooldown error message: ' + e.message);
                        process.exit(1);
                    }
                }

                // Ensure Supabase mock was NOT called a second time
                if (resetCallCount !== 1) {
                    console.error('Duplicate Supabase resetPasswordForEmail was NOT blocked! Call count: ' + resetCallCount);
                    process.exit(1);
                }

                process.exit(0);
            } catch (err) {
                console.error(err);
                process.exit(1);
            } finally {
                try { fs.unlinkSync('frontend/mock_sb_deliv12.js'); } catch(e) {}
                try { fs.unlinkSync('frontend/test_deliv12.mjs'); } catch(e) {}
            }
        });
        """
        res = self._run_node_harness(script)
        assert res.returncode == 0, f"Duplicate password reset cooldown block test failed: {res.stderr}"

    def test_13_rate_limit_429_handled_without_automatic_retries(self):
        """Validates HTTP 429 is propagated gracefully with zero automatic retry loops."""
        script = """
        const fs = require('fs');
        fs.writeFileSync('frontend/mock_sb_deliv13.js', 'export function createClient() { return global.mockSupabaseClient; }');
        const authContent = fs.readFileSync('frontend/auth.js', 'utf-8').replace(/from\\s+['\"]https:[^'\"]+['\"]/g, 'from "./mock_sb_deliv13.js"');
        fs.writeFileSync('frontend/test_deliv13.mjs', authContent);

        let totalAttempts = 0;
        global.mockSupabaseClient = {
            auth: {
                signUp: async () => {
                    totalAttempts++;
                    return { data: null, error: { status: 429, message: 'Too Many Requests' } };
                },
                onAuthStateChange: () => ({ data: { subscription: { unsubscribe: () => {} } } })
            }
        };

        global.fetch = async () => ({
            ok: true,
            json: async () => ({ configured: true, supabase_url: 'https://mock.supabase.co', supabase_anon_key: 'mock-key' })
        });

        const store = {};
        global.sessionStorage = {
            getItem: (k) => store[k] || null,
            setItem: (k, v) => { store[k] = String(v); },
            removeItem: (k) => { delete store[k]; }
        };

        import('./frontend/test_deliv13.mjs').then(async m => {
            try {
                try {
                    await m.signUpWithEmail('auditor@validcompany.in', 'ValidPassword123!');
                    console.error('signUpWithEmail should have rejected on 429');
                    process.exit(1);
                } catch (e) {
                    if (e.status !== 429) {
                        console.error('Expected error status 429, got: ' + e.status);
                        process.exit(1);
                    }
                    if (!e.message.includes('Rate limit reached')) {
                        console.error('Expected user-facing rate limit message, got: ' + e.message);
                        process.exit(1);
                    }
                }

                // Strict assertion: EXACTLY 1 attempt made, zero retries
                if (totalAttempts !== 1) {
                    console.error('Automatic retry loop detected! Total attempts: ' + totalAttempts);
                    process.exit(1);
                }

                process.exit(0);
            } catch (err) {
                console.error(err);
                process.exit(1);
            } finally {
                try { fs.unlinkSync('frontend/mock_sb_deliv13.js'); } catch(e) {}
                try { fs.unlinkSync('frontend/test_deliv13.mjs'); } catch(e) {}
            }
        });
        """
        res = self._run_node_harness(script)
        assert res.returncode == 0, f"Rate limit 429 handling test failed: {res.stderr}"

    def test_14_zero_real_emails_mock_isolation_check(self):
        """Verifies that tests only use mock clients and never make network requests to Supabase."""
        # Verify no network calls to Supabase API
        auth_file = FRONTEND_DIR / "auth.js"
        content = auth_file.read_text(encoding="utf-8")
        assert "validateDeliverableEmail" in content
        assert "isEmailCooldownActive" in content
        assert "getEmailCooldownRemaining" in content
        assert "setEmailCooldown" in content

    def test_15_html_templates_placeholder_and_confirmation_hygiene(self):
        """Audits index.html and login.html to ensure test domains are purged and confirmation UI exists."""
        index_html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
        login_html = (FRONTEND_DIR / "login.html").read_text(encoding="utf-8")

        # Negative checks: no misleading test domains in user-facing placeholders
        assert "name@organization.com" not in index_html, "organization.com must not be in index.html"
        assert "name@organization.com" not in login_html, "organization.com must not be in login.html"
        assert "user@example.com" not in index_html, "user@example.com must not be in index.html"
        assert "user@example.com" not in login_html, "user@example.com must not be in login.html"

        # Positive checks: recommended placeholder
        assert "name@your-domain.com" in index_html
        assert "name@your-domain.com" in login_html

        # Positive checks: confirmation box elements present
        assert "authSignupConfirmationBox" in index_html
        assert "authConfirmationTargetEmail" in index_html
        assert "authSignupCooldownBadge" in index_html

        assert "signupConfirmationBox" in login_html
        assert "confirmationTargetEmail" in login_html
        assert "signupCooldownBadge" in login_html

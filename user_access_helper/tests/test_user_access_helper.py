from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestUserAccessHelper(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = new_test_user(cls.env, login='uah_admin', groups='base.group_system,base.group_user')
        cls.target = new_test_user(cls.env, login='uah_target', groups='base.group_user', email='target@example.com')
        cls.other = new_test_user(cls.env, login='uah_other', groups='base.group_user')
        cls.Log = cls.env['user.access.log']

    def _wizard(self, mode, users, user=None, **vals):
        env = self.env(user=user or self.admin)
        return env['user.access.wizard'].create({'mode': mode, 'user_ids': [(6, 0, users.ids)], **vals})

    def _logs(self, action, users=None):
        domain = [('action', '=', action)]
        if users is not None:
            domain.append(('user_id', 'in', users.ids))
        return self.Log.search(domain)

    def _session(self, user, sid='uahsession', days_ago=0):
        when = fields.Datetime.now() - timedelta(days=days_ago)
        return self.env['res.device.log'].create({
            'session_identifier': sid, 'user_id': user.id, 'platform': 'linux', 'browser': 'chrome',
            'first_activity': when, 'last_activity': when, 'ip_address': '10.0.0.1', 'revoked': False})

    def _apikey(self, user, name='Integration'):
        expiry = fields.Datetime.now() + timedelta(days=30)
        return self.env['res.users.apikeys'].with_user(user)._generate(None, name, expiry)

    def _overview(self, user):
        self.env.flush_all()
        self.env['user.access.overview'].invalidate_model()
        return self.env['user.access.overview'].browse(user.id)

    # Passwords ------------------------------------------------------------

    def test_set_password_for_many_users_with_reason(self):
        users = self.target | self.other
        self._wizard('password', users, new_password='NewPass123', confirm_password='NewPass123',
                     reason='Ticket 42')._run()
        for user in users:
            # raises AccessDenied if the password was not changed
            self.env['res.users'].with_user(user)._check_credentials(
                {'type': 'password', 'password': 'NewPass123'}, {'interactive': False})
        logs = self._logs('password', users)
        self.assertEqual(logs.user_id, users)
        self.assertEqual(set(logs.mapped('reason')), {'Ticket 42'})
        self.assertEqual(logs.done_by_id, self.admin)

    def test_password_rules(self):
        with self.assertRaises(UserError):
            self._wizard('password', self.target, new_password='short', confirm_password='short')._run()
        with self.assertRaises(UserError):
            self._wizard('password', self.target, new_password='NewPass123', confirm_password='NewPass124')._run()
        self.assertFalse(self._logs('password', self.target))

    def test_generated_password_is_strong(self):
        wizard = self._wizard('password', self.target)
        wizard.action_generate_password()
        password = wizard.new_password
        self.assertEqual(len(password), 14)
        self.assertEqual(password, wizard.confirm_password)
        self.assertTrue(any(c.isupper() for c in password) and any(c.isdigit() for c in password))
        wizard._run()
        self.assertEqual(self._logs('password', self.target).details, 'Generated password')
        self.assertFalse(wizard.new_password or wizard.generated_password)

    def test_reset_email_skips_users_without_email(self):
        self.other.email = False
        with patch.object(type(self.env['res.users']), 'action_reset_password', autospec=True) as send:
            self._wizard('reset_email', self.target | self.other)._run()
        self.assertEqual(send.call_args[0][0], self.target)
        self.assertEqual(self._logs('reset_email', self.target | self.other).user_id, self.target)

    # 2FA, sessions, API keys ----------------------------------------------

    def test_disable_totp_only_logs_users_who_had_it(self):
        self.target.sudo().totp_secret = 'JBSWY3DPEHPK3PXP'
        self._wizard('totp', self.target | self.other)._run()
        self.target.invalidate_recordset(['totp_enabled'])
        self.assertFalse(self.target.totp_enabled)
        self.assertEqual(self._logs('totp', self.target | self.other).user_id, self.target)
        with self.assertRaises(UserError):
            self._wizard('totp', self.other)._run()

    def test_logout_revokes_sessions(self):
        log = self._session(self.target)
        self._wizard('logout', self.target)._run()
        self.assertTrue(log.revoked)
        self.assertEqual(self._logs('logout', self.target).details, '1 session(s) ended')

    def test_revoke_api_keys_keeps_trusted_devices_count_separate(self):
        self._apikey(self.target, 'ERP sync')
        self.assertEqual(self._overview(self.target).apikey_count, 1)
        self._wizard('apikeys', self.target)._run()
        self.assertFalse(self.env['res.users.apikeys'].search([('user_id', '=', self.target.id)]))
        self.assertEqual(self._logs('apikeys', self.target).details, 'Revoked: ERP sync')
        with self.assertRaises(UserError):
            self._wizard('apikeys', self.target)._run()

    # Offboarding -----------------------------------------------------------

    def test_deactivate_offboards_and_reactivate_restores(self):
        log = self._session(self.target)
        self._apikey(self.target)
        self._wizard('deactivate', self.target, reason='Left the company')._run()
        self.assertFalse(self.target.active)
        self.assertTrue(log.revoked)
        self.assertFalse(self.env['res.users.apikeys'].search([('user_id', '=', self.target.id)]))
        self.assertEqual(self._logs('deactivate', self.target).reason, 'Left the company')
        self._wizard('reactivate', self.target)._run()
        self.assertTrue(self.target.active)
        self.assertTrue(self._logs('reactivate', self.target))

    def test_cannot_lock_out_yourself_or_the_last_admin(self):
        with self.assertRaisesRegex(UserError, 'own account'):
            self._wizard('deactivate', self.admin)._run()
        # Run as the system user (like a script would): it is not counted as an
        # administrator, so deactivating every admin must be refused.
        admins = self.env.ref('base.group_system').users.filtered(lambda u: u.active and u.id != 1 and not u.share)
        with self.assertRaisesRegex(UserError, 'administrator must remain'):
            self._wizard('deactivate', admins, user=self.env.ref('base.user_root'))._run()
        self.assertTrue(all(admins.mapped('active')))

    # Rights ---------------------------------------------------------------

    def test_only_admins_can_run_actions(self):
        with self.assertRaises(AccessError):
            self._wizard('password', self.other, user=self.target,
                         new_password='NewPass123', confirm_password='NewPass123')._run()

    def test_apply_requires_identity_check(self):
        # Outside a browser session Odoo's check_identity refuses to run,
        # proving the Apply button is protected by the password re-check.
        wizard = self._wizard('password', self.target, new_password='NewPass123', confirm_password='NewPass123')
        with self.assertRaisesRegex(UserError, 'HTTP'):
            wizard.action_apply()

    def test_group_changes_are_logged_without_implied_groups(self):
        admin_group = self.env.ref('base.group_system')
        self.target.with_user(self.admin).write({'groups_id': [(4, admin_group.id)]})
        log = self._logs('groups', self.target)
        self.assertEqual(len(log), 1)
        self.assertTrue(log.admin_granted)
        self.assertEqual(log.details, 'Added: %s' % admin_group.full_name)
        self.assertEqual(log.done_by_id, self.admin)
        self.target.with_user(self.admin).write({'groups_id': [(3, admin_group.id)]})
        removed = self._logs('groups', self.target) - log
        self.assertIn('Removed: %s' % admin_group.full_name, removed.details)
        self.assertFalse(removed.admin_granted)

    def test_writes_without_group_changes_are_not_logged(self):
        self.target.write({'name': 'Renamed'})
        self.target.write({'groups_id': [(4, self.env.ref('base.group_user').id)]})  # already a member
        self.assertFalse(self._logs('groups', self.target))

    # Overview -------------------------------------------------------------

    def test_overview_flags_risks(self):
        self.target.sudo().totp_secret = False
        self.target.write({'groups_id': [(4, self.env.ref('base.group_system').id)]})
        self.assertEqual(self._overview(self.target).risk, 'high')
        self.assertEqual(self._overview(self.other).risk, 'never')
        self._session(self.other, days_ago=120)
        self.assertEqual(self._overview(self.other).risk, 'inactive')
        self.assertEqual(self._overview(self.other).session_count, 0)  # older than a session lives
        self._session(self.other, sid='fresh')
        row = self._overview(self.other)
        self.assertEqual((row.risk, row.session_count, row.days_inactive), ('ok', 1, 0))

    def test_actions_from_overview_rows_target_the_users(self):
        wizard = self.env['user.access.wizard'].with_user(self.admin).with_context(
            active_model='user.access.overview', active_ids=[self.target.id, self.other.id]).create({'mode': 'logout'})
        self.assertEqual(wizard.user_ids, self.target | self.other)

    def test_summary_counts_on_unsaved_dialog(self):
        self.target.sudo().totp_secret = 'JBSWY3DPEHPK3PXP'
        wizard = self.env(user=self.admin)['user.access.wizard'].new({
            'mode': 'totp', 'user_ids': [(6, 0, (self.target | self.other).ids)]})
        self.assertIn('1 of 2', wizard.summary)

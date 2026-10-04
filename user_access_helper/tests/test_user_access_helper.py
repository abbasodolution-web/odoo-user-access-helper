from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestUserAccessHelper(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = new_test_user(cls.env, login='uah_admin', groups='base.group_system,base.group_user')
        cls.target = new_test_user(cls.env, login='uah_target', groups='base.group_user')
        cls.other = new_test_user(cls.env, login='uah_other', groups='base.group_user')

    def _wizard(self, mode, users, user=None, **vals):
        env = self.env(user=user or self.admin)
        return env['user.access.wizard'].create({'mode': mode, 'user_ids': [(6, 0, users.ids)], **vals})

    def _logs(self, action):
        return self.env['user.access.log'].search([('action', '=', action), ('done_by_id', '=', self.admin.id)])

    def test_reset_password_for_many_users(self):
        users = self.target | self.other
        self._wizard('password', users, new_password='NewPass123', confirm_password='NewPass123')._run()
        for user in users:
            # raises AccessDenied if the password was not changed
            self.env['res.users'].with_user(user)._check_credentials('NewPass123', {'interactive': False})
        self.assertEqual(self._logs('password').user_id, users)

    def test_password_too_short(self):
        wizard = self._wizard('password', self.target, new_password='short', confirm_password='short')
        with self.assertRaises(UserError):
            wizard._run()

    def test_passwords_must_match(self):
        wizard = self._wizard('password', self.target, new_password='NewPass123', confirm_password='NewPass124')
        with self.assertRaises(UserError):
            wizard._run()
        self.assertFalse(self._logs('password'))

    def test_disable_totp(self):
        self.target.sudo().totp_secret = 'JBSWY3DPEHPK3PXP'
        self.assertTrue(self.target.totp_enabled)
        self._wizard('totp', self.target | self.other)._run()
        self.target.invalidate_recordset(['totp_enabled'])
        self.assertFalse(self.target.totp_enabled)
        # only the user who actually had 2FA is logged
        self.assertEqual(self._logs('totp').user_id, self.target)

    def test_disable_totp_needs_a_2fa_user(self):
        with self.assertRaises(UserError):
            self._wizard('totp', self.other)._run()

    def test_non_admin_cannot_use_wizard(self):
        with self.assertRaises(AccessError):
            self._wizard('password', self.other, user=self.target,
                         new_password='NewPass123', confirm_password='NewPass123')._run()

    def test_apply_requires_identity_check(self):
        # Outside a browser session Odoo's check_identity refuses to run,
        # proving the Apply button is protected by the password re-check.
        wizard = self._wizard('password', self.target, new_password='NewPass123', confirm_password='NewPass123')
        with self.assertRaisesRegex(UserError, 'HTTP'):
            wizard.action_apply()

    def test_dialog_counts_2fa_users_while_unsaved(self):
        # The browser opens the wizard as an unsaved record (onchange); the
        # 2FA counter must work there too.
        self.target.sudo().totp_secret = 'JBSWY3DPEHPK3PXP'
        wizard = self.env(user=self.admin)['user.access.wizard'].new({
            'mode': 'totp', 'user_ids': [(6, 0, (self.target | self.other).ids)]})
        self.assertEqual(wizard.totp_user_count, 1)

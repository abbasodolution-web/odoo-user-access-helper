from odoo import _, api, fields, models
from odoo.addons.base.models.res_users import check_identity
from odoo.exceptions import AccessError, UserError

MIN_PASSWORD_LENGTH = 8


class UserAccessWizard(models.TransientModel):
    _name = 'user.access.wizard'
    _description = 'Reset Password / Disable 2FA'

    mode = fields.Selection([
        ('password', 'Reset Password'),
        ('totp', 'Disable 2FA'),
    ], required=True, default='password')
    user_ids = fields.Many2many('res.users', string='Users', required=True)
    new_password = fields.Char()
    confirm_password = fields.Char()
    totp_user_count = fields.Integer(compute='_compute_totp_user_count')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'res.users' and 'user_ids' in fields_list:
            res['user_ids'] = [(6, 0, self.env.context.get('active_ids', []))]
        return res

    @api.depends('user_ids')
    def _compute_totp_user_count(self):
        for wizard in self:
            # user_ids are unsaved copies while the dialog is open; read 2FA on the real users
            wizard.totp_user_count = len(wizard.user_ids._origin.filtered('totp_enabled'))

    def _check_admin(self):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_("Only Settings administrators can manage user access."))

    def _log(self, users, action):
        self.env['user.access.log'].sudo().create([
            {'user_id': user.id, 'action': action, 'done_by_id': self.env.user.id} for user in users
        ])

    @check_identity
    def action_apply(self):
        # Same protection as Odoo's own 2FA button: the admin re-enters
        # their password before changing another user's access.
        return self._run()

    def _run(self):
        self.ensure_one()
        self._check_admin()
        if self.mode == 'password':
            return self._apply_password()
        return self._apply_totp()

    def _apply_password(self):
        if not self.new_password or len(self.new_password) < MIN_PASSWORD_LENGTH:
            raise UserError(_("The new password must be at least %s characters long.", MIN_PASSWORD_LENGTH))
        if self.new_password != self.confirm_password:
            raise UserError(_("The two passwords do not match."))
        for user in self.user_ids:
            user.password = self.new_password
        self._log(self.user_ids, 'password')
        return self._done(_("Password reset for %s user(s).", len(self.user_ids)))

    def _apply_totp(self):
        users = self.user_ids.filtered('totp_enabled')
        if not users:
            raise UserError(_("None of the selected users has two-factor authentication enabled."))
        # Identity was already checked on Apply; run the undecorated steps of
        # res.users.action_totp_disable() so the admin is not prompted twice.
        users._revoke_all_devices()
        users.sudo().write({'totp_secret': False})
        self._log(users, 'totp')
        return self._done(_("Two-factor authentication disabled for %s user(s).", len(users)))

    def _done(self, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': message,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

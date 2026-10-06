import secrets
import string

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.addons.base.models.res_users import check_identity
from odoo.exceptions import AccessError, UserError

MIN_PASSWORD_LENGTH = 8
GENERATED_PASSWORD_LENGTH = 14


class UserAccessWizard(models.TransientModel):
    _name = 'user.access.wizard'
    _description = 'User Access Actions'

    mode = fields.Selection([
        ('password', 'Set a new password'),
        ('reset_email', 'Send a password reset email'),
        ('totp', 'Disable two-factor authentication'),
        ('logout', 'Log out of all devices'),
        ('apikeys', 'Revoke API keys'),
        ('deactivate', 'Deactivate (offboarding)'),
        ('reactivate', 'Reactivate'),
    ], string='Action', required=True, default='password')
    user_ids = fields.Many2many('res.users', string='Users', required=True, context={'active_test': False})
    new_password = fields.Char()
    confirm_password = fields.Char()
    generated_password = fields.Char(readonly=True)
    reason = fields.Char(help="Saved in the User Access Log, e.g. a ticket number or \"Left the company\".")
    summary = fields.Html(compute='_compute_summary')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        model = self.env.context.get('active_model')
        if model in ('res.users', 'user.access.overview') and 'user_ids' in fields_list:
            # Overview rows have the same ids as their users
            res['user_ids'] = [(6, 0, self.env.context.get('active_ids', []))]
        return res

    # ------------------------------------------------------------------
    # What will happen
    # ------------------------------------------------------------------

    @api.depends('mode', 'user_ids')
    def _compute_summary(self):
        for wizard in self:
            # user_ids are unsaved copies while the dialog is open; read the real users
            users = wizard.user_ids._origin.sudo()
            wizard.summary = wizard._summary_text(users) if users else False

    def _summary_text(self, users):
        count = len(users)
        if self.mode == 'password':
            return _("The new password applies to %s user(s). Their other sessions are logged out "
                     "automatically; share the password with them safely.", count)
        if self.mode == 'reset_email':
            missing = users.filtered(lambda u: not u.email)
            text = _("%s user(s) receive an email with a link to choose a new password.", count - len(missing))
            if missing:
                text += ' ' + _("No email address: %s.", ', '.join(missing.mapped('name')))
            return text
        if self.mode == 'totp':
            with_totp = users.filtered('totp_enabled')
            return _("%(with)s of %(all)s selected user(s) have two-factor authentication. It will be turned off "
                     "and their trusted devices removed, so they can log in with their password and set it up "
                     "again.", **{'with': len(with_totp), 'all': count})
        if self.mode == 'logout':
            return _("%s open session(s) will be ended. The users must log in again on every device.",
                     len(self._devices(users)))
        if self.mode == 'apikeys':
            return _("%s API key(s) will be deleted. Integrations using them stop working at once.",
                     len(self._apikeys(users)))
        if self.mode == 'deactivate':
            return _("%s user(s) will be archived, logged out of every device and their API keys revoked. "
                     "Their records and history stay in place.", len(users.filtered('active')))
        return _("%s archived user(s) will be able to log in again.", len(users.filtered(lambda u: not u.active)))

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------

    def action_generate_password(self):
        self.ensure_one()
        alphabet = string.ascii_letters + string.digits + '!@#$%&*?'
        while True:
            password = ''.join(secrets.choice(alphabet) for _i in range(GENERATED_PASSWORD_LENGTH))
            if (any(c.islower() for c in password) and any(c.isupper() for c in password)
                    and any(c.isdigit() for c in password)):
                break
        self.write({'new_password': password, 'confirm_password': password, 'generated_password': password})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'name': _("Access Actions"),
        }

    @check_identity
    def action_apply(self):
        # Same protection as Odoo's own 2FA and device buttons: the admin
        # re-enters their password before changing another user's access.
        return self._run()

    def _run(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_("Only Settings administrators can manage user access."))
        if self.env.user.id != SUPERUSER_ID and self.user_ids._origin.filtered(lambda u: u.id == SUPERUSER_ID):
            raise UserError(_("The system user cannot be changed here."))
        message = getattr(self, '_apply_' + self.mode)(self.user_ids.sudo())
        return self._done(message)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _log(self, users, details=None):
        self.env['user.access.log']._record(users, self.mode, details=details, reason=self.reason)

    def _apply_password(self, users):
        if not self.new_password or len(self.new_password) < MIN_PASSWORD_LENGTH:
            raise UserError(_("The new password must be at least %s characters long.", MIN_PASSWORD_LENGTH))
        if self.new_password != self.confirm_password:
            raise UserError(_("The two passwords do not match."))
        if users.filtered(lambda u: not u.active):
            raise UserError(_("Reactivate archived users before setting their password."))
        for user in users:
            user.password = self.new_password
        generated = self.generated_password and self.generated_password == self.new_password
        # Do not keep the password in the dialog record until it is vacuumed
        self.write({'new_password': False, 'confirm_password': False, 'generated_password': False})
        self._log(users, details=_("Generated password") if generated else False)
        return _("Password set for %s user(s).", len(users))

    def _apply_reset_email(self, users):
        users = users.filtered('email')
        if not users:
            raise UserError(_("None of the selected users has an email address."))
        if users.filtered(lambda u: not u.active):
            raise UserError(_("Reactivate archived users before sending them a reset email."))
        users.action_reset_password()
        self._log(users, details=lambda u: self.env._("Sent to %s", u.email))
        return _("Password reset email sent to %s user(s).", len(users))

    def _apply_totp(self, users):
        users = users.filtered('totp_enabled')
        if not users:
            raise UserError(_("None of the selected users has two-factor authentication enabled."))
        # Identity was checked on Apply; run the steps of action_totp_disable()
        # directly so the admin is not prompted twice.
        users._revoke_all_devices()
        users.write({'totp_secret': False})
        self._log(users)
        return _("Two-factor authentication disabled for %s user(s).", len(users))

    def _devices(self, users):
        # res.device is a SQL view over the device log: write pending log lines first
        self.env['res.device.log'].flush_model()
        devices = self.env['res.device'].sudo().search([('user_id', 'in', users.ids)])
        # Never end the session the admin is using right now
        return devices.filtered(lambda d: not d.is_current)

    def _apikeys(self, users):
        return self.env['res.users.apikeys'].sudo().search([
            ('user_id', 'in', users.ids), ('scope', '!=', 'browser')])

    def _apply_logout(self, users):
        devices = self._devices(users)
        counts = {user: len(devices.filtered(lambda d: d.user_id == user)) for user in users}
        devices._revoke()
        users._revoke_all_devices()  # 2FA trusted devices must ask for a code again
        self._log(users, details=lambda u: self.env._("%s session(s) ended", counts[u]))
        return _("%(sessions)s session(s) ended for %(users)s user(s).", sessions=len(devices), users=len(users))

    def _apply_apikeys(self, users):
        keys = self._apikeys(users)
        if not keys:
            raise UserError(_("None of the selected users has an API key."))
        names = {user: keys.filtered(lambda k: k.user_id == user).mapped('name') for user in users}
        keys._remove()
        users = users.filtered(lambda u: names[u])
        self._log(users, details=lambda u: self.env._("Revoked: %s", ', '.join(names[u])))
        return _("%(keys)s API key(s) revoked for %(users)s user(s).", keys=len(keys), users=len(users))

    def _apply_deactivate(self, users):
        users = users.filtered('active')
        if not users:
            raise UserError(_("The selected users are already archived."))
        if self.env.user in users:
            raise UserError(_("You cannot deactivate your own account."))
        admins = self.env.ref('base.group_system').sudo().users.filtered(
            lambda u: u.active and u.id != SUPERUSER_ID and not u.share)
        if admins and not (admins - users):
            raise UserError(_("At least one active administrator must remain."))
        self._devices(users)._revoke()
        users._revoke_all_devices()
        self._apikeys(users)._remove()
        users.write({'active': False})
        self._log(users)
        return _("%s user(s) deactivated.", len(users))

    def _apply_reactivate(self, users):
        users = users.filtered(lambda u: not u.active)
        if not users:
            raise UserError(_("The selected users are already active."))
        users.write({'active': True})
        self._log(users)
        return _("%s user(s) reactivated.", len(users))

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

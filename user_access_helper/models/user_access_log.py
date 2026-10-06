from odoo import api, fields, models
from odoo.http import request

ACTIONS = [
    ('password', 'Password set'),
    ('reset_email', 'Reset email sent'),
    ('totp', '2FA disabled'),
    ('logout', 'Logged out of all devices'),
    ('apikeys', 'API keys revoked'),
    ('deactivate', 'Deactivated'),
    ('reactivate', 'Reactivated'),
    ('groups', 'Access rights changed'),
]


class UserAccessLog(models.Model):
    _name = 'user.access.log'
    _description = 'User Access Log'
    _order = 'create_date desc, id desc'
    _rec_name = 'action'

    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade', readonly=True,
                              index=True, context={'active_test': False})
    action = fields.Selection(ACTIONS, required=True, readonly=True)
    details = fields.Text(readonly=True)
    reason = fields.Char(readonly=True)
    admin_granted = fields.Boolean(string='Admin rights granted', readonly=True,
                                   help="This change gave the user Settings administrator rights.")
    done_by_id = fields.Many2one('res.users', string='Done By', required=True, readonly=True,
                                 default=lambda self: self.env.user, context={'active_test': False})
    ip_address = fields.Char(string='IP Address', readonly=True)
    create_date = fields.Datetime(string='Date', readonly=True)

    @api.model
    def _record(self, users, action, details=None, reason=None, admin_granted=False):
        """Log one line per user. Called with sudo by the wizard and the users write."""
        ip = request.httprequest.remote_addr if request else False
        return self.sudo().create([{
            'user_id': user.id,
            'action': action,
            'details': details(user) if callable(details) else details,
            'reason': reason or False,
            'admin_granted': admin_granted,
            'done_by_id': self.env.user.id,
            'ip_address': ip,
        } for user in users])

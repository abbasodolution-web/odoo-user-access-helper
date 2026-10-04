from odoo import fields, models


class UserAccessLog(models.Model):
    _name = 'user.access.log'
    _description = 'User Access Log'
    _order = 'create_date desc, id desc'
    _rec_name = 'action'

    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade', readonly=True)
    action = fields.Selection([
        ('password', 'Password reset'),
        ('totp', '2FA disabled'),
    ], required=True, readonly=True)
    done_by_id = fields.Many2one('res.users', string='Done By', required=True, readonly=True,
                                 default=lambda self: self.env.user)
    create_date = fields.Datetime(string='Date', readonly=True)

from odoo import fields, models, tools
from odoo.tools import SQL

INACTIVE_DAYS = 90


class UserAccessOverview(models.Model):
    """One row per user (same id as the user), so actions selected here run
    on the users themselves."""
    _name = 'user.access.overview'
    _description = 'User Security Overview'
    _auto = False
    _order = 'risk_sequence, last_login desc nulls last'
    _rec_name = 'user_id'

    user_id = fields.Many2one('res.users', string='User', readonly=True, context={'active_test': False})
    login = fields.Char(readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    active = fields.Boolean(readonly=True)
    user_type = fields.Selection([('internal', 'Internal'), ('portal', 'Portal / Public')], readonly=True)
    is_admin = fields.Boolean(string='Administrator', readonly=True)
    totp_enabled = fields.Boolean(string='2FA', readonly=True)
    last_login = fields.Datetime(string='Last Seen', readonly=True,
                                 help="Latest login or activity of this user in any session.")
    days_inactive = fields.Integer(string='Idle Days', readonly=True, aggregator='max')
    session_count = fields.Integer(string='Sessions', readonly=True,
                                   help="Devices with a session that has not been logged out or revoked.")
    apikey_count = fields.Integer(string='API Keys', readonly=True)
    risk = fields.Selection([
        ('high', 'Admin without 2FA'),
        ('inactive', 'Unused account'),
        ('never', 'Never logged in'),
        ('ok', 'OK'),
    ], readonly=True)
    risk_sequence = fields.Integer(readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(SQL("""
            CREATE OR REPLACE VIEW %(table)s AS (
                WITH admin_group AS (
                    SELECT res_id AS id FROM ir_model_data
                     WHERE module = 'base' AND name = 'group_system'
                ), seen AS (
                    SELECT u.id AS user_id,
                           GREATEST(
                               (SELECT MAX(l.create_date) FROM res_users_log l WHERE l.create_uid = u.id),
                               (SELECT MAX(d.last_activity) FROM res_device_log d WHERE d.user_id = u.id)
                           ) AS last_login
                      FROM res_users u
                ), base AS (
                    SELECT u.id,
                           u.id AS user_id,
                           u.login,
                           u.company_id,
                           u.active,
                           CASE WHEN u.share THEN 'portal' ELSE 'internal' END AS user_type,
                           EXISTS (SELECT 1 FROM res_groups_users_rel r, admin_group g
                                    WHERE r.uid = u.id AND r.gid = g.id) AS is_admin,
                           (u.totp_secret IS NOT NULL AND u.totp_secret != 'false') AS totp_enabled,
                           s.last_login,
                           (CURRENT_DATE - s.last_login::date) AS days_inactive,
                           (SELECT COUNT(DISTINCT d.session_identifier) FROM res_device_log d
                             WHERE d.user_id = u.id AND d.revoked IS NOT TRUE
                               AND d.last_activity > (NOW() AT TIME ZONE 'UTC') - INTERVAL '7 days') AS session_count,
                           (SELECT COUNT(*) FROM res_users_apikeys k
                             WHERE k.user_id = u.id AND k.scope IS DISTINCT FROM 'browser'
                               AND (k.expiration_date IS NULL OR k.expiration_date > NOW() AT TIME ZONE 'UTC')
                           ) AS apikey_count
                      FROM res_users u
                      JOIN seen s ON s.user_id = u.id
                     WHERE u.id != 1
                )
                SELECT base.*,
                       CASE WHEN is_admin AND NOT totp_enabled THEN 'high'
                            WHEN last_login IS NULL THEN 'never'
                            WHEN days_inactive >= %(days)s THEN 'inactive'
                            ELSE 'ok' END AS risk,
                       CASE WHEN is_admin AND NOT totp_enabled THEN 1
                            WHEN last_login IS NULL THEN 3
                            WHEN days_inactive >= %(days)s THEN 2
                            ELSE 4 END AS risk_sequence
                  FROM base
            )""", table=SQL.identifier(self._table), days=INACTIVE_DAYS))

    def action_open_user(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.users',
            'res_id': self.user_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

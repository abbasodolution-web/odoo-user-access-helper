from odoo import models


def _touches_groups(values):
    return any(key == 'groups_id' or key.startswith(('in_group_', 'sel_groups_')) for key in values)


class ResUsers(models.Model):
    _inherit = 'res.users'

    def write(self, values):
        if not _touches_groups(values) or self.env.context.get('install_mode'):
            return super().write(values)
        before = {user.id: user.sudo().groups_id for user in self}
        res = super().write(values)
        self._access_log_group_changes(before)
        return res

    def _access_log_group_changes(self, before):
        """Log the groups each user gained or lost.

        Only the groups that were chosen are listed: groups that come along
        because they are implied by another one ("Administrator" brings
        dozens) would bury the change that matters.
        """
        admin = self.env.ref('base.group_system')
        Log = self.env['user.access.log']
        for user in self.sudo():
            old, new = before[user.id], user.groups_id
            added, removed = new - old, old - new
            added -= added.trans_implied_ids
            removed -= removed.trans_implied_ids
            if not added and not removed:
                continue
            lines = [self.env._("Added: %s", name) for name in added.mapped('full_name')]
            lines += [self.env._("Removed: %s", name) for name in removed.mapped('full_name')]
            Log._record(user, 'groups', details='\n'.join(lines),
                        admin_granted=admin in (new - old) and admin not in old)

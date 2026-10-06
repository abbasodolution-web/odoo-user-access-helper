{
    'name': 'User Access Helper',
    'version': '18.0.2.0.0',
    'category': 'Administration',
    'summary': 'Security overview of your users, bulk access actions (passwords, 2FA, sessions, API keys, '
               'offboarding) and an audit log of every access change',
    'description': """
User Access Helper
==================
Everyday user security for administrators, from the Users list:

* Security Overview: every user's 2FA, admin rights, last login, open sessions and API keys,
  with risk flags (admins without 2FA, accounts unused for 90 days)
* Bulk actions with a reason: set a password, send a reset email, disable 2FA, log out of
  all devices, revoke API keys, deactivate (offboarding) and reactivate
* Access rights changes are logged automatically: who added or removed which group, and when
* One audit log for everything, with IP address and reason
* Safe by design: password re-check, cannot lock yourself or the last administrator out
""",
    'author': 'ABBAS',
    'maintainer': 'ABBAS',
    'support': 'abbasodolution@gmail.com',
    'license': 'LGPL-3',
    'depends': ['base', 'auth_totp', 'auth_signup'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/user_access_wizard_views.xml',
        'views/user_access_log_views.xml',
        'views/user_access_overview_views.xml',
        'views/menus.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
}

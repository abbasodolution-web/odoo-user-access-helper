{
    'name': 'User Access Helper',
    'version': '17.0.1.0.0',
    'category': 'Administration',
    'summary': 'Reset passwords and disable 2FA for selected users, with an audit log',
    'description': """
User Access Helper
==================
Support tasks for administrators, straight from the Users list:

* Reset the password of one or many users at once
* Disable two-factor authentication for users who lost their device
* Every action is recorded in an audit log (who, for whom, when)
* Available to Settings administrators only
""",
    'author': 'ABBAS',
    'maintainer': 'ABBAS',
    'support': 'abbasodolution@gmail.com',
    'license': 'LGPL-3',
    'depends': ['base', 'auth_totp'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/user_access_wizard_views.xml',
        'views/user_access_log_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
}

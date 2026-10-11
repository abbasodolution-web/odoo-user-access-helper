# User Access Helper — Odoo 18 (v2)

![User Access Helper](user_access_helper/static/description/banner.png)

See which user accounts are a risk, fix them in bulk, and keep a record of every access change —
from **Settings › Users & Companies**.

## Features
- **Security Overview**: every user's admin rights, 2FA, last seen, idle days, open sessions and API keys
- **Risk flags**: Admin without 2FA, Unused account (90+ days), Never logged in — sorted to the top, with filters
- **Access Actions** for one user or many (Users list or Overview):
  set or generate a strong password, send a reset email, disable 2FA, log out of all devices,
  revoke API keys, deactivate (offboarding: archive + end sessions + revoke keys) and reactivate
- **A reason on every action** and a live summary before you apply
- **Access rights change log**: group added/removed on any user is recorded automatically, admin grants flagged;
  only the chosen groups are listed, not the ones they imply
- **One audit log**: what, for whom, by whom, when, IP address and reason
- **Safe by design**: Odoo's password re-check before every change; you cannot deactivate yourself or the
  last administrator, and your own session is never ended
- Settings administrators only; depends on `base`, `auth_totp`, `auth_signup`; 16 automated tests

## Install
Copy `user_access_helper` into your addons path, update the Apps list and install **User Access Helper**.
Odoo 17 version: branch [`17.0`](../../tree/17.0).

## Available for Odoo 17, 18, 19 and 20

| Odoo | Price | Get it |
|---|---|---|
| 17 (v1) | Free (LGPL-3) | [Odoo Apps Store](https://apps.odoo.com/apps/modules/17.0/user_access_helper) |
| 18 (v2) | Free (LGPL-3) | [Odoo Apps Store](https://apps.odoo.com/apps/modules/18.0/user_access_helper) |
| 19 (v3) | $29 (one-time, OPL-1) | [Odoo Apps Store](https://apps.odoo.com/apps/modules/19.0/user_access_helper) |
| 20 | Coming soon | In development |

## Author
**ABBAS** — custom Odoo development (Odoo 17, 18, 19 & 20). Support: abbasodolution@gmail.com

License: LGPL-3

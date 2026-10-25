# Security, RTS Returns Manager

Local demo posture, stated plainly. This version runs on one machine for a
station desk; it is not hardened for the public internet.

- Passwords are stored as PBKDF2 hashes with a per-user salt. The seed's demo
  passwords (rtsdesk / demo1234, deskview / view1234) are printed in the
  README on purpose and must be changed before the app holds real returns.
- Every route except login and health sits behind a bearer token. Roles
  separate the supervisor desk from the read-only viewer, and admin-only
  routes (backup) refuse viewers.
- All SQL is parameterised. A reship decision is refused by the backend until
  a customer contact attempt is logged on the return.
- Errors are structured JSON; the API does not leak stack traces or SQL.
- CSV import is capped at 500 KB, validates its header as a whole, and names
  rejected rows instead of guessing at them.

Not done, on purpose, for a local demo: no TLS, no rate limiting on login,
tokens live in server memory and die with the process. Put it behind a real
proxy and a real secret before it leaves the building.

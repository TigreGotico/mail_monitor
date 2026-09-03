# mail_monitor

A small utility to watch an IMAP mailbox for new email and react to it in Python.
It has no dependencies outside the Python standard library.

It has two pieces:

- `EmailClient` — logs into an IMAP server and fetches emails (all, unseen, or
  already-seen), optionally filtered to a sender whitelist.
- `EmailMonitor` — a background `Thread` that polls `EmailClient` on an
  interval and calls a callback for each new email.

## Install

```bash
pip install mail_monitor
```

## Usage

```python
from mail_monitor import EmailMonitor

mail = "me@example.com"
password = "app-password"  # use an app password, not your real password

monitor = EmailMonitor(mail, password, time_between_checks=30)


def new_email(email):
    print(email["sender"], email["subject"], email["payload"])


monitor.on_new_email = new_email
monitor.start()  # runs in a background thread
```

Each email is delivered as a dict: `{"sender", "email", "payload", "ts", "subject"}`.
`payload` is always plain text: a multipart message's `text/plain` part is
used when present, and an HTML-only message is stripped of markup with a
small stdlib parser.

## IMAP configuration

`EmailMonitor` and `EmailClient` default to Gmail (`imap.gmail.com:993`, folder
`inbox`). Gmail requires IMAP access to be enabled and an
[app password](https://myaccount.google.com/apppasswords) — a regular Google
account password will not work. For other providers, pass `address` and
`port` for their IMAP server.

```python
EmailMonitor(mail, password, address="imap.example.com", port=993)
```

Never hardcode credentials in source — load them from environment variables
or a secrets file that is not committed.

## License

Apache-2.0.

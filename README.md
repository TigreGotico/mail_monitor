# mail_monitor

Simple utility to monitor an IMAP mailbox for new emails and hand them to a
callback, plus a small helper for reading email bodies (HTML or plain text).

## Install

```bash
pip install mail_monitor
```

## Usage

```python
from mail_monitor import EmailMonitor


class MyMonitor(EmailMonitor):
    def on_new_email(self, email):
        print(email["sender"], email["subject"], email["payload"])


mon = MyMonitor("me@example.com", "app-password", address="imap.gmail.com")
mon.start()
```

`EmailClient` exposes the underlying IMAP calls (`list_new_emails`,
`list_old_emails`, `mark_all_read`) if you want to poll manually instead of
running the background thread.

## License

Apache-2.0

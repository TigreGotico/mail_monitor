import unittest
from unittest.mock import MagicMock, patch

from mail_monitor import EmailClient, EmailMonitor


def _fake_raw_email(from_addr="Someone <someone@example.com>", subject="Hi",
                     body="hello world"):
    return (
        f"From: {from_addr}\r\n"
        f"To: me@example.com\r\n"
        f"Subject: {subject}\r\n"
        f"Received: from mx.example.com\r\n"
        f"\tMon, 01 Jan 2024 12:00:00 +0000\r\n"
        f"\r\n{body}\r\n"
    ).encode("utf-8")


class TestEmailClient(unittest.TestCase):
    @patch("mail_monitor.imaplib.IMAP4_SSL")
    def test_list_new_emails(self, mock_imap_cls):
        mock_imap = MagicMock()
        mock_imap_cls.return_value = mock_imap
        mock_imap.search.return_value = ("OK", [b"1"])
        mock_imap.fetch.return_value = ("OK", [(b"1", _fake_raw_email())])

        client = EmailClient("me@example.com", "secret")
        emails = client.list_new_emails()

        mock_imap.login.assert_called_once_with("me@example.com", "secret")
        mock_imap.select.assert_called_once_with("inbox")
        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0]["email"], "someone@example.com")
        self.assertEqual(emails[0]["subject"], "Hi")
        self.assertIn("hello world", emails[0]["payload"])

    @patch("mail_monitor.imaplib.IMAP4_SSL")
    def test_whitelist_filters_senders(self, mock_imap_cls):
        mock_imap = MagicMock()
        mock_imap_cls.return_value = mock_imap
        mock_imap.search.return_value = ("OK", [b"1"])
        mock_imap.fetch.return_value = (
            "OK", [(b"1", _fake_raw_email(from_addr="Nope <nope@example.com>"))]
        )

        client = EmailClient("me@example.com", "secret")
        emails = client.list_new_emails(whitelist=["someone@example.com"])

        self.assertEqual(emails, [])

    @patch("mail_monitor.imaplib.IMAP4_SSL")
    def test_mark_as_seen_flag(self, mock_imap_cls):
        mock_imap = MagicMock()
        mock_imap_cls.return_value = mock_imap
        mock_imap.search.return_value = ("OK", [b"1"])
        mock_imap.fetch.return_value = ("OK", [(b"1", _fake_raw_email())])

        client = EmailClient("me@example.com", "secret")
        client.list_new_emails(mark_as_seen=True)

        mock_imap.store.assert_called_once_with(b"1", "+FLAGS", "\\SEEN")


class TestEmailMonitor(unittest.TestCase):
    def test_defaults_and_stop(self):
        monitor = EmailMonitor("me@example.com", "secret", time_between_checks=1)
        self.assertIsInstance(monitor.email, EmailClient)
        self.assertFalse(monitor.stop_event.is_set())
        monitor.stop()
        self.assertTrue(monitor.stop_event.is_set())


if __name__ == "__main__":
    unittest.main()

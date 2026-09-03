import unittest
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import MagicMock, patch

from mail_monitor import EmailClient, html_to_text

RECEIVED = "Wed, 03 Sep 2026 12:00:00 +0000"


def _plain_message():
    msg = MIMEText("hello world", "plain")
    msg["From"] = "Alice <alice@example.com>"
    msg["Subject"] = "Hi"
    msg["Received"] = RECEIVED
    return msg


def _multipart_message():
    msg = MIMEMultipart("alternative")
    msg["From"] = "Bob <bob@example.com>"
    msg["Subject"] = "Multipart"
    msg["Received"] = RECEIVED
    msg.attach(MIMEText("plain body", "plain"))
    msg.attach(MIMEText("<p>html body</p>", "html"))
    return msg


def _html_only_message():
    msg = MIMEText("<p>Hello <b>World</b></p><br>Line2", "html")
    msg["From"] = "Carol <carol@example.com>"
    msg["Subject"] = "HTML only"
    msg["Received"] = RECEIVED
    return msg


def _make_imap_mock(messages, search_result=b""):
    """messages: list of email.message.Message, indexed by fetch id."""
    mock_imap = MagicMock()
    mock_imap.login.return_value = ("OK", [b""])
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.search.return_value = ("OK", [search_result])

    def fetch(num, spec):
        idx = int(num) - 1
        raw = messages[idx].as_bytes()
        return "OK", [(b"1 (RFC822 {%d})" % len(raw), raw)]

    mock_imap.fetch.side_effect = fetch
    return mock_imap


class TestGetBody(unittest.TestCase):
    def test_plain_text_body(self):
        self.assertEqual(EmailClient.get_body(_plain_message()), "hello world")

    def test_multipart_prefers_text_plain(self):
        body = EmailClient.get_body(_multipart_message())
        self.assertEqual(body, "plain body")

    def test_html_only_is_stripped_with_stdlib(self):
        body = EmailClient.get_body(_html_only_message())
        self.assertIn("Hello World", body)
        self.assertIn("Line2", body)
        self.assertNotIn("<p>", body)
        self.assertNotIn("<b>", body)

    def test_html_to_text_helper(self):
        text = html_to_text("<div>a &amp; b</div>")
        self.assertEqual(text, "a & b")


class TestListEmails(unittest.TestCase):
    def test_list_new_emails_parses_messages(self):
        messages = [_plain_message()]
        mock_imap = _make_imap_mock(messages, search_result=b"1")
        with patch("mail_monitor.imaplib.IMAP4_SSL", return_value=mock_imap):
            client = EmailClient("user", "pass")
            result = client.list_new_emails()

        self.assertEqual(len(result), 1)
        mail = result[0]
        self.assertEqual(mail["email"], "alice@example.com")
        self.assertEqual(mail["sender"], "Alice")
        self.assertEqual(mail["subject"], "Hi")
        self.assertEqual(mail["payload"], "hello world")

    def test_list_new_emails_empty_unseen_short_circuits(self):
        mock_imap = _make_imap_mock([], search_result=b"")
        with patch("mail_monitor.imaplib.IMAP4_SSL", return_value=mock_imap):
            client = EmailClient("user", "pass")
            result = client.list_new_emails()

        self.assertEqual(result, [])
        mock_imap.fetch.assert_not_called()
        mock_imap.close.assert_called_once()
        mock_imap.logout.assert_called_once()

    def test_mark_as_seen_true_stores_plus_flags(self):
        messages = [_plain_message()]
        mock_imap = _make_imap_mock(messages, search_result=b"1")
        with patch("mail_monitor.imaplib.IMAP4_SSL", return_value=mock_imap):
            client = EmailClient("user", "pass")
            client.list_new_emails(mark_as_seen=True)

        mock_imap.store.assert_called_once_with(b"1", "+FLAGS", "\\SEEN")

    def test_mark_as_seen_false_stores_minus_flags(self):
        messages = [_plain_message()]
        mock_imap = _make_imap_mock(messages, search_result=b"1")
        with patch("mail_monitor.imaplib.IMAP4_SSL", return_value=mock_imap):
            client = EmailClient("user", "pass")
            client.list_new_emails(mark_as_seen=False)

        mock_imap.store.assert_called_once_with(b"1", "-FLAGS", "\\SEEN")

    def test_whitelist_filters_sender(self):
        messages = [_plain_message()]
        mock_imap = _make_imap_mock(messages, search_result=b"1")
        with patch("mail_monitor.imaplib.IMAP4_SSL", return_value=mock_imap):
            client = EmailClient("user", "pass")
            result = client.list_new_emails(whitelist=["nobody@example.com"])

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()

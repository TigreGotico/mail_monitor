import imaplib
import email
import email.header
import email.utils
from html.parser import HTMLParser
from time import sleep, mktime
from threading import Thread, Event


class _HTMLTextExtractor(HTMLParser):
    """Minimal stdlib HTML-to-text extractor.

    Not a full renderer: drops tags/attributes/styles and keeps the
    visible text, which is all `EmailClient.get_body` needs for an
    HTML-only email.
    """

    _SKIP_TAGS = {"script", "style", "head", "title"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._chunks = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        elif tag in ("br", "p", "div", "tr", "li"):
            self._chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth and data:
            self._chunks.append(data)

    def get_text(self):
        text = "".join(self._chunks)
        lines = [" ".join(line.split()) for line in text.splitlines()]
        lines = [line for line in lines if line]
        return "\n".join(lines).strip()


def html_to_text(html):
    """Convert an HTML string to plain text using only the stdlib."""
    parser = _HTMLTextExtractor()
    parser.feed(html or "")
    parser.close()
    return parser.get_text()


class EmailClient:
    def __init__(self, account, password, address="imap.gmail.com",
                 port=993, folder="inbox"):
        self.account = account
        self.password = password
        self.port = port
        self.address = address
        self.folder = folder

    def list_old_emails(self, whitelist=None):
        return self.list_emails(whitelist, mark_as_seen=False,
                                search_filter="(SEEN)")

    def list_new_emails(self, whitelist=None, mark_as_seen=False):
        return self.list_emails(whitelist, mark_as_seen,
                                search_filter="(UNSEEN)")

    def list_emails(self, whitelist=None, mark_as_seen=False,
                    search_filter="(ALL)"):
        """
        Returns new emails.
        output:
        dicts in the format :{name,sender,subject}
        whitelist: the a list of emails that it will return
        """
        M = imaplib.IMAP4_SSL(str(self.address), port=int(self.port))
        M.login(str(self.account), str(self.password))  # Login
        M.select(str(self.folder))

        rv, data = M.search(None, search_filter)  # Only get unseen/unread emails
        new_emails = []
        for num in data[0].split():
            rv, data = M.fetch(num, '(RFC822)')

            msg = email.message_from_bytes(data[0][1])

            from_email = email.utils.parseaddr(msg['From'])[1]
            subject = str(msg['Subject'])
            sender = str(msg['From'])
            payload = self.get_body(msg)

            ts = email.utils.parsedate(msg['Received'].split("\n")[-1].strip())
            ts = mktime(ts)

            is_in_whitelist = not whitelist or from_email in whitelist

            if not is_in_whitelist:
                # The user does not want emails from that sender, skip it
                continue
            if "<" in sender:
                mail = sender.split("<")[1].split(">")[0]
                sender = sender.split("<")[0].strip()
            else:
                mail = sender
            mail = {"sender": sender,
                    "email": mail,
                    "payload": payload,
                    "ts": ts,
                    "subject": subject}
            if mark_as_seen:
                M.store(num, "+FLAGS", '\\SEEN')
            else:
                # Some email providers automatically mark a message as seen: undo that
                M.store(num, "-FLAGS", '\\SEEN')

            new_emails.append(mail)
        # Clean up
        M.close()
        M.logout()

        return list(new_emails)

    def mark_all_read(self):
        self.list_new_emails(mark_as_seen=True)

    @staticmethod
    def get_body(msg):
        if msg.is_multipart():
            plain_part = None
            html_part = None
            for part in msg.walk():
                content_type = part.get_content_type()
                if part.get_content_maintype() == "multipart":
                    continue
                if content_type == "text/plain" and plain_part is None:
                    plain_part = part
                elif content_type == "text/html" and html_part is None:
                    html_part = part
            if plain_part is not None:
                return _get_part_text(plain_part).strip()
            if html_part is not None:
                return html_to_text(_get_part_text(html_part)).strip()
            payload = msg.get_payload()
            if isinstance(payload, list) and payload:
                return _get_part_text(payload[-1]).strip()
            return str(payload).strip()

        content_type = msg.get_content_type()
        text = _get_part_text(msg)
        if content_type == "text/html":
            return html_to_text(text).strip()
        return text.strip()

    def send(self, subject, email, body):
        raise NotImplementedError


def _get_part_text(part):
    """Decode a message/part payload to a str, handling charset/CTE."""
    payload = part.get_payload(decode=True)
    if payload is None:
        payload = part.get_payload()
        return payload if isinstance(payload, str) else str(payload)
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, TypeError):
        return payload.decode("utf-8", errors="replace")


class EmailMonitor(Thread):
    """
    enable less secure apps https://myaccount.google.com/lesssecureapps
    enable imap  https://mail.google.com/mail/u/1/?tab=mm#settings/fwdandpop
    """
    def __init__(self, mail, password, address="imap.gmail.com", port=993,
                 folder="inbox", time_between_checks=30, whitelist=None,
                 mark_as_seen = True, filter="(UNSEEN)"):
        super().__init__()
        self.mark_as_seen = mark_as_seen
        self.time_between_checks = time_between_checks
        self.whitelist = whitelist
        self.filter = filter
        self.email = EmailClient(mail, password, address, port, folder)
        self.stop_event = Event()

    def run(self):
        self.stop_event.clear()
        while not self.stop_event.is_set():

            mails = self.email.list_emails(self.whitelist,
                                           self.mark_as_seen,
                                           search_filter=self.filter)
            for mail in mails:
                self.on_new_email(mail)
            sleep(self.time_between_checks)

    def on_new_email(self, email):
        print("new email", email)

    def stop(self):
        self.stop_event.set()

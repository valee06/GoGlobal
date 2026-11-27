import os
from unittest import skipUnless

from smtplib import SMTPRecipientsRefused
from unittest.mock import patch


from django.core import mail
from django.test import SimpleTestCase, override_settings

from accounts.emails import MailResult, send_code_email, send_email

class SendCodeEmailTests(SimpleTestCase):
    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="test@goglobal.local",
        EMAIL_CODE_TTL_MINUTES=10,
    )
    def test_sends_verification_code(self):
        send_code_email("student@example.invalid", "123456", "email_verify")

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["student@example.invalid"])
        self.assertIn("123456", mail.outbox[0].body)

    def test_rejects_unknown_purpose(self):
        with self.assertRaises(ValueError):
            send_code_email("student@example.invalid", "123456", "unknown")

    @patch("accounts.emails.send_mail", return_value=1)
    def test_smtp_acceptance_is_reported(self, send_mail_mock):
        result = send_code_email(
            "student@example.invalid", "123456", "email_verify"
        )

        self.assertEqual(result.value, "accepted")

    @patch(
        "accounts.emails.send_mail",
        side_effect=SMTPRecipientsRefused({}),
    )
    def test_smtp_refusal_is_reported(self, send_mail_mock):
        result = send_code_email(
            "student@example.invalid", "123456", "email_verify"
        )

        self.assertEqual(result.value, "rejected")

    @patch(
        "accounts.emails.send_mail",
        side_effect=TimeoutError(),
    )
    def test_timeout_is_reported_as_unknown(self, send_mail_mock):
        result = send_code_email(
            "student@example.invalid", "123456", "email_verify"
        )

        self.assertEqual(result.value, "unknown")

@skipUnless(
    os.getenv("RUN_SMTP_INTEGRATION_TESTS") == "1",
    "Запускается только при явном включении SMTP-проверки",
)
class MailpitIntegrationTests(SimpleTestCase):
    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="127.0.0.1",
        EMAIL_PORT=1025,
        EMAIL_USE_TLS=False,
        EMAIL_USE_SSL=False,
        EMAIL_TIMEOUT=3,
    )
    def test_mailpit_accepts_message(self):
        result = send_email(
            "smtp-test@example.invalid",
            "GoGlobal SMTP integration test",
            "Проверка локального SMTP-приёмника.",
        )

        self.assertIs(result, MailResult.ACCEPTED)
from django.core.management.base import BaseCommand
from django.core.mail import send_mail, EmailMessage
from django.conf import settings
import socket
import smtplib


class Command(BaseCommand):
    help = "Test SMTP email configuration by sending a test email"

    def add_arguments(self, parser):
        parser.add_argument(
            "recipient_email",
            type=str,
            help="Email address to send the test email to",
        )
        parser.add_argument(
            "--test-connection-only",
            action="store_true",
            help="Only test SMTP connection without sending email",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed SMTP configuration",
        )

    def handle(self, *args, **options):
        recipient = options["recipient_email"]
        test_only = options.get("test_connection_only", False)
        verbose = options.get("verbose", False)

        self.stdout.write("Testing email configuration...")

        # Display current configuration
        if verbose:
            self.stdout.write("\nCurrent email configuration:")
            self.stdout.write(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
            self.stdout.write(f"EMAIL_HOST: {settings.EMAIL_HOST}")
            self.stdout.write(f"EMAIL_PORT: {settings.EMAIL_PORT}")
            self.stdout.write(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
            self.stdout.write(
                f"EMAIL_USE_SSL: {getattr(settings, 'EMAIL_USE_SSL', False)}"
            )
            self.stdout.write(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
            self.stdout.write(
                f"EMAIL_HOST_PASSWORD: {'*' * len(settings.EMAIL_HOST_PASSWORD) if settings.EMAIL_HOST_PASSWORD else '(not set)'}"
            )
            self.stdout.write(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
            self.stdout.write(
                f"SERVER_EMAIL: {getattr(settings, 'SERVER_EMAIL', settings.DEFAULT_FROM_EMAIL)}"
            )
            self.stdout.write(f"BACKEND_URL: {settings.BACKEND_URL}")

        # Test SMTP connection
        if test_only:
            self.stdout.write("\nTesting SMTP connection only...")
            try:
                # Test DNS resolution
                self.stdout.write(f"Resolving {settings.EMAIL_HOST}...")
                socket.gethostbyname(settings.EMAIL_HOST)
                self.stdout.write(self.style.SUCCESS(f"✓ DNS resolution successful"))

                # Test SMTP connection
                self.stdout.write(f"Connecting to SMTP server...")
                if settings.EMAIL_USE_TLS:
                    server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT)
                    server.starttls()
                elif getattr(settings, "EMAIL_USE_SSL", False):
                    server = smtplib.SMTP_SSL(settings.EMAIL_HOST, settings.EMAIL_PORT)
                else:
                    server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT)

                if settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD:
                    self.stdout.write("Authenticating...")
                    server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
                    self.stdout.write(self.style.SUCCESS("✓ Authentication successful"))

                server.quit()
                self.stdout.write(self.style.SUCCESS("✓ SMTP connection successful"))

            except socket.gaierror as e:
                self.stdout.write(self.style.ERROR(f"✗ DNS resolution failed: {e}"))
                return
            except smtplib.SMTPAuthenticationError as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ SMTP authentication failed: {e}")
                )
                return
            except smtplib.SMTPException as e:
                self.stdout.write(self.style.ERROR(f"✗ SMTP error: {e}"))
                return
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Connection failed: {e}"))
                return

        else:
            # Send test email
            self.stdout.write(f"\nSending test email to {recipient}...")
            try:
                subject = "ProEnergia - Test Email"
                message = f"""
This is a test email from ProEnergia.

If you receive this email, your SMTP configuration is working correctly.

Configuration details:
- SMTP Host: {settings.EMAIL_HOST}
- SMTP Port: {settings.EMAIL_PORT}
- TLS: {settings.EMAIL_USE_TLS}
- From: {settings.DEFAULT_FROM_EMAIL}
- Backend URL: {settings.BACKEND_URL}

This email was sent using the Django email backend: {settings.EMAIL_BACKEND}
"""
                html_message = f"""
<html>
<body>
<h2>ProEnergia - Test Email</h2>
<p>This is a test email from <b>ProEnergia</b>.</p>
<p>If you receive this email, your SMTP configuration is working correctly.</p>

<h3>Configuration details:</h3>
<ul>
    <li>SMTP Host: {settings.EMAIL_HOST}</li>
    <li>SMTP Port: {settings.EMAIL_PORT}</li>
    <li>TLS: {settings.EMAIL_USE_TLS}</li>
    <li>From: {settings.DEFAULT_FROM_EMAIL}</li>
    <li>Backend URL: {settings.BACKEND_URL}</li>
</ul>

<p><small>This email was sent using the Django email backend: {settings.EMAIL_BACKEND}</small></p>
</body>
</html>
"""

                # Create email with HTML content
                email = EmailMessage(
                    subject=subject,
                    body=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[recipient],
                )
                email.content_subtype = "html"
                email.body = html_message

                # Send the email
                email.send(fail_silently=False)

                self.stdout.write(
                    self.style.SUCCESS(f"✓ Test email sent successfully to {recipient}")
                )
                self.stdout.write(
                    "\nPlease check your inbox (and spam folder) for the test email."
                )

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Failed to send email: {e}"))
                self.stdout.write("\nTroubleshooting tips:")
                self.stdout.write("1. Check your email configuration in the .env file")
                self.stdout.write("2. Ensure the EMAIL_HOST and EMAIL_PORT are correct")
                self.stdout.write(
                    "3. Verify EMAIL_HOST_USER and EMAIL_HOST_PASSWORD are valid"
                )
                self.stdout.write(
                    "4. For AWS SES, ensure your domain/email is verified"
                )
                self.stdout.write(
                    "5. For AWS SES, check if you're still in sandbox mode"
                )
                self.stdout.write(
                    "6. Check firewall rules for outbound SMTP connections"
                )

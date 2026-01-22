#!/usr/bin/env python3
"""
GitHub Webhook Listener for ProEnergia Deployment
Listens for push events on the main branch and triggers deployment
"""

import hashlib
import hmac
import json
import logging
import os
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Configuration
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")  # Set this in environment
DEPLOY_SCRIPT = "/usr/local/bin/deploy-proenergia"
LISTEN_PORT = 9001
LISTEN_HOST = "127.0.0.1"  # Only listen on localhost, nginx will proxy

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/var/log/proenergia/webhook.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class WebhookHandler(BaseHTTPRequestHandler):
    """Handle GitHub webhook requests"""

    def do_POST(self):
        """Process POST requests from GitHub"""
        if self.path != "/webhook":
            self.send_error(404)
            return

        try:
            # Read the request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            # Verify webhook signature
            if WEBHOOK_SECRET:
                signature = self.headers.get("X-Hub-Signature-256", "")
                if not self.verify_signature(body, signature):
                    logger.warning("Invalid webhook signature")
                    self.send_error(401, "Invalid signature")
                    return

            # Parse the JSON payload
            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                logger.error("Invalid JSON payload")
                self.send_error(400, "Invalid JSON")
                return

            # Check if this is a push to main branch
            if self.should_deploy(payload):
                logger.info("Deployment triggered by push to main branch")
                self.trigger_deployment()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Deployment triggered")
            else:
                logger.info("Webhook received but deployment not triggered")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Webhook received, no action taken")

        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            self.send_error(500, "Internal server error")

    def do_GET(self):
        """Health check endpoint"""
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Webhook listener is running")
        else:
            self.send_error(404)

    def verify_signature(self, payload, signature):
        """Verify the webhook signature from GitHub"""
        if not signature.startswith("sha256="):
            return False

        expected = (
            "sha256="
            + hmac.new(
                WEBHOOK_SECRET.encode("utf-8"), payload, hashlib.sha256
            ).hexdigest()
        )

        return hmac.compare_digest(expected, signature)

    def should_deploy(self, payload):
        """Check if the webhook should trigger a deployment"""
        # Check if it's a push event
        event_type = self.headers.get("X-GitHub-Event", "")
        if event_type != "push":
            return False

        # Check if it's the main branch
        ref = payload.get("ref", "")
        if ref != "refs/heads/main":
            return False

        # Could add more checks here (e.g., specific commit messages, authors, etc.)
        return True

    def trigger_deployment(self):
        """Execute the deployment script"""
        try:
            # Run deployment in background to avoid blocking the webhook response
            subprocess.Popen(
                ["sudo", DEPLOY_SCRIPT],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
            logger.info("Deployment script started")
        except Exception as e:
            logger.error(f"Failed to trigger deployment: {e}")
            raise

    def log_message(self, format, *args):
        """Override to use our logger"""
        logger.info(format % args)


def main():
    """Start the webhook listener"""
    if not WEBHOOK_SECRET:
        logger.warning(
            "WEBHOOK_SECRET not set - webhook signatures will not be verified!"
        )
        logger.warning("Set WEBHOOK_SECRET environment variable for production use")

    server = HTTPServer((LISTEN_HOST, LISTEN_PORT), WebhookHandler)
    logger.info(f"Webhook listener started on {LISTEN_HOST}:{LISTEN_PORT}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Webhook listener stopped")
        server.server_close()


if __name__ == "__main__":
    main()

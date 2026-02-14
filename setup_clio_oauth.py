#!/usr/bin/env python3
"""
Clio OAuth Setup Helper for Pflug Law Lead Qualifier.
Helps obtain and refresh Clio API tokens.
"""

import os
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests
import json

# Configuration - update these values
CLIO_CLIENT_ID = os.getenv("CLIO_CLIENT_ID", "")
CLIO_CLIENT_SECRET = os.getenv("CLIO_CLIENT_SECRET", "")
REDIRECT_URI = "http://localhost:8088/callback"
SCOPES = "contacts matters custom_fields users"


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle the OAuth callback."""

    def do_GET(self):
        """Process the callback with authorization code."""
        parsed = urlparse(self.path)

        if parsed.path == "/callback":
            params = parse_qs(parsed.query)

            if "code" in params:
                self.server.auth_code = params["code"][0]
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"""
                    <html>
                    <body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h1 style="color: green;">Authorization Successful!</h1>
                    <p>You can close this window and return to the terminal.</p>
                    </body>
                    </html>
                """)
            elif "error" in params:
                self.server.auth_code = None
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                error = params.get("error_description", ["Unknown error"])[0]
                self.wfile.write(f"""
                    <html>
                    <body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h1 style="color: red;">Authorization Failed</h1>
                    <p>{error}</p>
                    </body>
                    </html>
                """.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def get_authorization_code():
    """Start OAuth flow and get authorization code."""
    # Build authorization URL
    auth_url = (
        f"https://app.clio.com/oauth/authorize"
        f"?response_type=code"
        f"&client_id={CLIO_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={SCOPES}"
    )

    print("\nOpening browser for Clio authorization...")
    print(f"If browser doesn't open, visit: {auth_url}\n")

    webbrowser.open(auth_url)

    # Start local server to receive callback
    server = HTTPServer(("localhost", 8088), OAuthCallbackHandler)
    server.auth_code = None

    print("Waiting for authorization callback...")
    while server.auth_code is None:
        server.handle_request()

    return server.auth_code


def exchange_code_for_tokens(auth_code):
    """Exchange authorization code for access and refresh tokens."""
    response = requests.post(
        "https://app.clio.com/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIO_CLIENT_ID,
            "client_secret": CLIO_CLIENT_SECRET,
        },
    )

    if response.status_code != 200:
        print(f"Error getting tokens: {response.text}")
        return None

    return response.json()


def refresh_tokens(refresh_token):
    """Refresh access token using refresh token."""
    response = requests.post(
        "https://app.clio.com/oauth/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLIO_CLIENT_ID,
            "client_secret": CLIO_CLIENT_SECRET,
        },
    )

    if response.status_code != 200:
        print(f"Error refreshing tokens: {response.text}")
        return None

    return response.json()


def test_token(access_token):
    """Test that the token works."""
    response = requests.get(
        "https://app.clio.com/api/v4/users/who_am_i",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    if response.status_code == 200:
        user = response.json().get("data", {})
        return user.get("name", "Unknown")
    return None


def main():
    """Main entry point."""
    print("=" * 60)
    print("  Clio OAuth Setup Helper")
    print("=" * 60)

    if not CLIO_CLIENT_ID or not CLIO_CLIENT_SECRET:
        print("\nError: CLIO_CLIENT_ID and CLIO_CLIENT_SECRET must be set.")
        print("Either set them as environment variables or edit this script.")
        print("\nTo get these values:")
        print("1. Go to https://app.clio.com/settings/developer_applications")
        print("2. Create a new application")
        print("3. Copy the Client ID and Client Secret")
        sys.exit(1)

    print("\nOptions:")
    print("1. Get new access token (full OAuth flow)")
    print("2. Refresh existing token")
    print("3. Test existing token")
    print()

    choice = input("Enter choice (1/2/3): ").strip()

    if choice == "1":
        # Full OAuth flow
        auth_code = get_authorization_code()

        if not auth_code:
            print("Failed to get authorization code")
            sys.exit(1)

        print("\nExchanging code for tokens...")
        tokens = exchange_code_for_tokens(auth_code)

        if not tokens:
            print("Failed to get tokens")
            sys.exit(1)

        print("\n" + "=" * 60)
        print("  SUCCESS! Add these to your .env file:")
        print("=" * 60)
        print(f"\nCLIO_ACCESS_TOKEN={tokens['access_token']}")
        print(f"CLIO_REFRESH_TOKEN={tokens['refresh_token']}")
        print()

        # Test it
        user = test_token(tokens["access_token"])
        if user:
            print(f"Token verified! Authenticated as: {user}")

    elif choice == "2":
        # Refresh token
        refresh_token = input("Enter your refresh token: ").strip()

        if not refresh_token:
            print("Refresh token is required")
            sys.exit(1)

        print("\nRefreshing token...")
        tokens = refresh_tokens(refresh_token)

        if not tokens:
            print("Failed to refresh token")
            sys.exit(1)

        print("\n" + "=" * 60)
        print("  SUCCESS! Update these in your .env file:")
        print("=" * 60)
        print(f"\nCLIO_ACCESS_TOKEN={tokens['access_token']}")
        if "refresh_token" in tokens:
            print(f"CLIO_REFRESH_TOKEN={tokens['refresh_token']}")
        print()

    elif choice == "3":
        # Test existing token
        access_token = os.getenv("CLIO_ACCESS_TOKEN") or input("Enter access token: ").strip()

        if not access_token:
            print("Access token is required")
            sys.exit(1)

        print("\nTesting token...")
        user = test_token(access_token)

        if user:
            print(f"Token is valid! Authenticated as: {user}")
        else:
            print("Token is invalid or expired")
            sys.exit(1)

    else:
        print("Invalid choice")
        sys.exit(1)


if __name__ == "__main__":
    main()

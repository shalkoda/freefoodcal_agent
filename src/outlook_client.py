"""
Microsoft Outlook Email Client
Handles authentication and email retrieval via Microsoft Graph API
"""

import os
import requests
from msal import ConfidentialClientApplication
from bs4 import BeautifulSoup
from typing import List, Dict, Optional


class OutlookClient:
    """
    Microsoft Outlook client using Graph API

    Handles:
    - OAuth authentication
    - Email search
    - Email content retrieval
    - HTML stripping
    """

    def __init__(self):
        self.client_id = os.getenv('MICROSOFT_CLIENT_ID')
        self.client_secret = os.getenv('MICROSOFT_CLIENT_SECRET')
        self.tenant_id = os.getenv('MICROSOFT_TENANT_ID', 'common')
        self.redirect_uri = os.getenv('MICROSOFT_REDIRECT_URI')

        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.scopes = ["https://graph.microsoft.com/.default"]

        self.graph_endpoint = "https://graph.microsoft.com/v1.0"

        self.app = ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret
        )

        self.access_token = None

    def get_auth_url(self):
        """
        Get authorization URL for OAuth flow

        Returns:
            str: Authorization URL to redirect user to
        """
        auth_url = self.app.get_authorization_request_url(
            scopes=["User.Read", "Mail.Read"],
            redirect_uri=self.redirect_uri
        )
        return auth_url

    def authenticate(self, auth_code):
        """
        Exchange authorization code for access token

        Args:
            auth_code: Authorization code from OAuth callback

        Returns:
            dict: Token response
        """
        result = self.app.acquire_token_by_authorization_code(
            auth_code,
            scopes=["User.Read", "Mail.Read"],
            redirect_uri=self.redirect_uri
        )

        if "access_token" in result:
            self.access_token = result["access_token"]
            return result
        else:
            raise Exception(f"Authentication failed: {result.get('error_description')}")

    def get_access_token(self):
        """
        Get current access token (acquire silently if needed)

        Returns:
            str: Access token
        """
        if self.access_token:
            return self.access_token

        # Try to get token silently from cache
        accounts = self.app.get_accounts()
        if accounts:
            result = self.app.acquire_token_silent(
                scopes=["User.Read", "Mail.Read"],
                account=accounts[0]
            )
            if result and "access_token" in result:
                self.access_token = result["access_token"]
                return self.access_token

        # Need to re-authenticate
        raise Exception("No valid access token. Please re-authenticate.")

    def search_emails(self, query, max_results=50):
        """
        Search emails with a query string

        Args:
            query: Search query (e.g., "food OR pizza OR lunch")
            max_results: Maximum number of results to return

        Returns:
            List[Dict]: List of email metadata
        """
        token = self.get_access_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

        # Build search query
        search_url = f"{self.graph_endpoint}/me/messages"
        params = {
            '$search': f'"{query}"',
            '$select': 'id,subject,from,receivedDateTime,bodyPreview',
            '$top': max_results,
            '$orderby': 'receivedDateTime DESC'
        }

        try:
            response = requests.get(search_url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()
            emails = []

            for item in data.get('value', []):
                emails.append({
                    'id': item['id'],
                    'subject': item.get('subject', ''),
                    'sender': item.get('from', {}).get('emailAddress', {}).get('address', ''),
                    'sender_name': item.get('from', {}).get('emailAddress', {}).get('name', ''),
                    'received_at': item.get('receivedDateTime', ''),
                    'preview': item.get('bodyPreview', '')
                })

            return emails

        except requests.exceptions.RequestException as e:
            print(f"❌ Error searching emails: {e}")
            return []

    def get_email_content(self, email_id):
        """
        Get full email content

        Args:
            email_id: Email ID

        Returns:
            str: Email body text (HTML stripped)
        """
        token = self.get_access_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

        url = f"{self.graph_endpoint}/me/messages/{email_id}"
        params = {
            '$select': 'body,subject,from,receivedDateTime'
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()
            body = data.get('body', {})

            # Get content and content type
            content = body.get('content', '')
            content_type = body.get('contentType', 'text')

            # Strip HTML if needed
            if content_type == 'html':
                content = self._strip_html(content)

            return content

        except requests.exceptions.RequestException as e:
            print(f"❌ Error getting email content: {e}")
            return None

    def _strip_html(self, html_content):
        """
        Strip HTML tags from email content

        Args:
            html_content: HTML string

        Returns:
            str: Plain text
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text
            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)

            return text

        except Exception as e:
            print(f"⚠️  Error stripping HTML: {e}")
            return html_content

    def get_user_info(self):
        """Get current user info"""
        token = self.get_access_token()
        headers = {'Authorization': f'Bearer {token}'}

        try:
            response = requests.get(f"{self.graph_endpoint}/me", headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Error getting user info: {e}")
            return None

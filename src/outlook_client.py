"""
Microsoft Outlook Email Client
Handles authentication and email retrieval via Microsoft Graph API
"""

import os
import json
import requests
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from msal import ConfidentialClientApplication, SerializableTokenCache


# ---- OAuth / Graph settings ----
SCOPES = ["User.Read", "Mail.Read", "offline_access", "openid", "profile"]
CACHE_PATH = os.getenv("MS_MICROSOFT_CACHE", "microsoft_token_cache.bin")
GRAPH_ROOT = "https://graph.microsoft.com/v1.0"


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
        self.client_id = os.getenv("MICROSOFT_CLIENT_ID")
        self.client_secret = os.getenv("MICROSOFT_CLIENT_SECRET")
        self.tenant_id = os.getenv("MICROSOFT_TENANT_ID", "common")
        self.redirect_uri = os.getenv("MICROSOFT_REDIRECT_URI")

        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"

        # ---- Token cache persisted to disk so silent auth works across restarts ----
        self.cache = SerializableTokenCache()
        if os.path.exists(CACHE_PATH):
            try:
                with open(CACHE_PATH, "r") as f:
                    self.cache.deserialize(f.read())
            except Exception:
                # Corrupt cache? Start fresh.
                self.cache = SerializableTokenCache()

        self.app = ConfidentialClientApplication(
            self.client_id,
            authority=self.authority,
            client_credential=self.client_secret,
            token_cache=self.cache,
        )

        self.access_token: Optional[str] = None

    # --------- helpers ---------
    def _persist_cache(self) -> None:
        if self.cache.has_state_changed:
            with open(CACHE_PATH, "w") as f:
                f.write(self.cache.serialize())

    # --------- OAuth flow ---------
    def get_auth_url(self) -> str:
        """
        Get authorization URL for OAuth flow.
        User should be redirected here to consent.
        """
        return self.app.get_authorization_request_url(
            scopes=SCOPES,
            redirect_uri=self.redirect_uri,
        )

    def authenticate(self, auth_code: str) -> Dict:
        """
        Exchange authorization code for tokens and persist cache.
        """
        result = self.app.acquire_token_by_authorization_code(
            auth_code,
            scopes=SCOPES,
            redirect_uri=self.redirect_uri,
        )
        if "access_token" in result:
            self.access_token = result["access_token"]
            self._persist_cache()
            return result
        raise Exception(f"Authentication failed: {result.get('error_description')}")

    def get_access_token(self) -> str:
        """
        Get a valid access token.
        Tries in-memory first, then silent (refresh) using the persisted cache.
        """
        if self.access_token:
            return self.access_token

        accounts = self.app.get_accounts()
        if accounts:
            result = self.app.acquire_token_silent(scopes=SCOPES, account=accounts[0])
            if result and "access_token" in result:
                self.access_token = result["access_token"]
                self._persist_cache()
                return self.access_token

        # Need interactive auth
        raise Exception("No valid access token. Please re-authenticate.")

    def sign_out(self) -> None:
        """Optional helper to clear the cached token and force re-auth."""
        try:
            if os.path.exists(CACHE_PATH):
                os.remove(CACHE_PATH)
        except Exception:
            pass
        self.cache = SerializableTokenCache()
        self.app.token_cache = self.cache
        self.access_token = None

    # --------- Graph calls ---------
    def search_emails(self, query: str, max_results: int = 50) -> List[Dict]:
        """
        Search emails with a full-text query across subject/body.
        Uses Graph $search POST endpoint (requires ConsistencyLevel: eventual).

        Args:
            query: e.g. 'food OR pizza OR lunch'
            max_results: max messages to return

        Returns:
            List[Dict]: simplified email metadata
        """
        try:
            token = self.get_access_token()
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            print(f"   Please authenticate via the web interface: /auth/microsoft/login")
            return []

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "ConsistencyLevel": "eventual",  # REQUIRED for $search
        }

        # Use POST endpoint for search with request body
        url = f"{GRAPH_ROOT}/me/messages/$search"
        
        # Request body for search
        search_body = {
            "requests": [
                {
                    "entityTypes": ["message"],
                    "query": {
                        "queryString": query
                    },
                    "from": 0,
                    "size": max_results
                }
            ]
        }

        try:
            resp = requests.post(url, headers=headers, json=search_body, timeout=20)
            resp.raise_for_status()
            data = resp.json()

            emails: List[Dict] = []
            
            # Handle search response format
            # The response may have a different structure depending on Graph API version
            # Try to extract from value array first
            if "value" in data:
                items = data["value"]
            elif isinstance(data, list):
                items = data
            else:
                # Search API might return hits differently
                items = data.get("hits", {}).get("hits", [])
                # Extract _source if it's Elasticsearch-like format
                if items and "_source" in items[0]:
                    items = [hit.get("_source", {}) for hit in items]

            for item in items:
                # Handle different response formats
                email_data = item.get("_source", item) if "_source" in item else item
                
                emails.append({
                    "id": email_data.get("id", ""),
                    "subject": email_data.get("subject", ""),
                    "sender": email_data.get("from", {}).get("emailAddress", {}).get("address", "") if isinstance(email_data.get("from"), dict) else "",
                    "sender_name": email_data.get("from", {}).get("emailAddress", {}).get("name", "") if isinstance(email_data.get("from"), dict) else "",
                    "received_at": email_data.get("receivedDateTime", ""),
                    "preview": email_data.get("bodyPreview", ""),
                })
            
            # If search POST doesn't work, fallback to $filter with GET
            if not emails:
                return self._search_emails_fallback(query, max_results, token)

            return emails

        except requests.exceptions.HTTPError as e:
            # If POST search fails, try fallback method
            if e.response.status_code in [400, 404, 405]:
                print(f"⚠️  Search POST endpoint not available, trying fallback method...")
                return self._search_emails_fallback(query, max_results, token)
            print(f"❌ Error searching emails: {e}")
            if e.response.status_code == 401:
                print(f"   Authentication expired. Please re-authenticate.")
            return []
        except requests.exceptions.RequestException as e:
            print(f"❌ Error searching emails: {e}")
            # Try fallback method
            return self._search_emails_fallback(query, max_results, token)

    def _search_emails_fallback(self, query: str, max_results: int, token: str) -> List[Dict]:
        """
        Fallback method using $filter for email search.
        Uses OData $filter syntax to search in subject and bodyPreview.
        """
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # Build filter query - search in subject or bodyPreview
        # Note: Graph API doesn't support full-text search in $filter, so we'll
        # fetch recent emails and filter client-side, or use contains for subject
        url = f"{GRAPH_ROOT}/me/messages"
        
        # Extract keywords from query for basic filtering
        keywords = [kw.strip() for kw in query.replace("OR", " ").replace("AND", " ").split() if kw.strip()]
        
        # Use contains filter for subject (limited but works)
        if keywords:
            # Build filter: contains(subject, 'keyword1') or contains(subject, 'keyword2')...
            filter_parts = [f"contains(subject, '{kw}')" for kw in keywords[:3]]  # Limit to 3 keywords
            filter_query = " or ".join(filter_parts)
            params = {
                "$filter": filter_query,
                "$select": "id,subject,from,receivedDateTime,bodyPreview",
                "$top": max_results * 2,  # Get more to filter client-side
                "$orderby": "receivedDateTime DESC",
            }
        else:
            # No keywords, just get recent emails
            params = {
                "$select": "id,subject,from,receivedDateTime,bodyPreview",
                "$top": max_results,
                "$orderby": "receivedDateTime DESC",
            }

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()

            emails: List[Dict] = []
            query_lower = query.lower()
            
            for item in data.get("value", []):
                # Client-side filtering if needed
                subject = item.get("subject", "").lower()
                preview = item.get("bodyPreview", "").lower()
                
                # Check if email matches query (simple keyword matching)
                if any(keyword.lower() in subject or keyword.lower() in preview for keyword in keywords):
                    emails.append({
                        "id": item["id"],
                        "subject": item.get("subject", ""),
                        "sender": item.get("from", {}).get("emailAddress", {}).get("address", ""),
                        "sender_name": item.get("from", {}).get("emailAddress", {}).get("name", ""),
                        "received_at": item.get("receivedDateTime", ""),
                        "preview": item.get("bodyPreview", ""),
                    })
                    
                    if len(emails) >= max_results:
                        break

            return emails

        except requests.exceptions.RequestException as e:
            print(f"❌ Error in fallback search: {e}")
            return []

    def get_email_content(self, email_id: str) -> Optional[str]:
        """
        Get full email content for a message id, stripping HTML into text.
        """
        token = self.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        url = f"{GRAPH_ROOT}/me/messages/{email_id}"
        params = {"$select": "body,subject,from,receivedDateTime"}

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=20)
            resp.raise_for_status()
            body = resp.json().get("body", {})

            content = body.get("content", "") or ""
            content_type = body.get("contentType", "text")
            if content_type.lower() == "html":
                return self._strip_html(content)
            return content

        except requests.exceptions.RequestException as e:
            print(f"❌ Error getting email content: {e}")
            return None

    def get_user_info(self) -> Optional[Dict]:
        """Fetch the current user's profile."""
        token = self.get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        try:
            resp = requests.get(f"{GRAPH_ROOT}/me", headers=headers, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Error getting user info: {e}")
            return None

    # --------- utilities ---------
    def _strip_html(self, html_content: str) -> str:
        """
        Strip HTML tags from email content to plain text.
        """
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text()
            # Normalize whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            return "\n".join(chunk for chunk in chunks if chunk)
        except Exception as e:
            print(f"⚠️  Error stripping HTML: {e}")
            return html_content

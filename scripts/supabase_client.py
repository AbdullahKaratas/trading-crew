#!/usr/bin/env python3
"""
Supabase REST Client for Portfolio Management.

Uses Supabase REST API for CRUD operations on the portfolios table.
"""

import os
from typing import Optional
import requests


class SupabaseClient:
    """REST client for Supabase portfolio operations."""

    def __init__(self):
        """Initialize with environment variables."""
        self.url = os.environ.get("SUPABASE_URL")
        self.key = os.environ.get("SUPABASE_SERVICE_KEY")

        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _request(self, method: str, endpoint: str, data: dict = None, params: dict = None) -> dict:
        """Make a request to Supabase REST API."""
        url = f"{self.url}/rest/v1/{endpoint}"

        response = requests.request(
            method=method,
            url=url,
            headers=self.headers,
            json=data,
            params=params,
        )

        if not response.ok:
            print(f"Supabase error: {response.status_code} - {response.text[:200]}")
            response.raise_for_status()

        if response.text:
            return response.json()
        return {}

    def get_portfolio(self, user_id: str) -> list:
        """Get all positions for a user."""
        params = {
            "user_id": f"eq.{user_id}",
            "order": "created_at.asc",
        }
        result = self._request("GET", "portfolios", params=params)
        return result if isinstance(result, list) else []

    def upsert_position(self, position: dict) -> dict:
        """Insert or update a position (upsert on unique constraint)."""
        # Use Supabase upsert with on_conflict
        headers = self.headers.copy()
        headers["Prefer"] = "return=representation,resolution=merge-duplicates"

        url = f"{self.url}/rest/v1/portfolios"

        response = requests.post(
            url=url,
            headers=headers,
            json=position,
        )

        if not response.ok:
            print(f"Supabase upsert error: {response.status_code} - {response.text[:200]}")
            response.raise_for_status()

        result = response.json()
        return result[0] if isinstance(result, list) and result else result

    def upsert_positions(self, user_id: str, positions: list) -> list:
        """Upsert multiple positions for a user."""
        results = []
        for pos in positions:
            pos["user_id"] = user_id
            result = self.upsert_position(pos)
            results.append(result)
        return results

    def remove_position(self, user_id: str, symbol: str) -> bool:
        """Remove a position by symbol (all directions/knockouts)."""
        params = {
            "user_id": f"eq.{user_id}",
            "symbol": f"eq.{symbol}",
        }
        self._request("DELETE", "portfolios", params=params)
        return True

    def clear_portfolio(self, user_id: str) -> bool:
        """Remove all positions for a user."""
        params = {
            "user_id": f"eq.{user_id}",
        }
        self._request("DELETE", "portfolios", params=params)
        return True

    def update_position(self, position_id: str, updates: dict) -> dict:
        """Update a specific position by ID."""
        params = {
            "id": f"eq.{position_id}",
        }
        updates["updated_at"] = "now()"
        result = self._request("PATCH", "portfolios", data=updates, params=params)
        return result[0] if isinstance(result, list) and result else result


def get_supabase_client() -> Optional[SupabaseClient]:
    """Get Supabase client if credentials are available."""
    try:
        return SupabaseClient()
    except ValueError as e:
        print(f"Supabase not configured: {e}")
        return None

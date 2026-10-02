"""
repository.py
In-Memory Mock-Backend für Bestellungen und Retourenbuchungen.
"""

from datetime import datetime, timedelta
import json
import os
from typing import Any, Dict, List, Optional
import uuid


class MockOrderRepository:
    """
    Mock-Repository zur Simulation einer relationalen Datenbasis (Accounts, Bestellungen, Bestelldetails)
    und Retouren-Operationen.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        if not db_path:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(base_dir, "data", "database.json")
        self.db_path = db_path
        self._accounts: Dict[str, Dict[str, Any]] = {}
        self._orders: Dict[str, Dict[str, Any]] = {}
        self._order_items: List[Dict[str, Any]] = []
        self._returns: Dict[str, Dict[str, Any]] = {}
        self._load_database()

    def _load_database(self) -> None:
        now = datetime.now()
        loaded = False
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._accounts = data.get("accounts", {})
                    raw_orders = data.get("bestellungen", {})
                    self._order_items = data.get("bestelldetails", [])

                    # Konvertiere in internes Format mit Kaufdatum
                    for oid, o in raw_orders.items():
                        days_ago = o.get("datum_tage_her", 5)
                        account_id = o.get("account")
                        account = self._accounts.get(account_id, {})
                        
                        items_for_order = [
                            {
                                "item_id": it.get("artikelnummer", "ART-000"),
                                "name": it.get("bezeichnung", "Artikel"),
                                "price": float(it.get("preis", 0.0))
                            }
                            for it in self._order_items
                            if it.get("bestellnummer") == oid
                        ]
                        total = sum(
                            float(it.get("preis", 0))
                            for it in self._order_items
                            if it.get("bestellnummer") == oid
                        ) or 99.0

                        self._orders[oid] = {
                            "order_id": oid,
                            "customer_email": account.get("email", "kunde@example.com"),
                            "purchase_date": now - timedelta(days=days_ago),
                            "account_id": account_id,
                            "items": items_for_order or [{"item_id": "ART-000", "name": "Standardartikel", "price": 99.0}],
                            "total_amount": round(total, 2),
                            "currency": "EUR",
                            "adresse": o.get("adresse", account.get("adresse", "")),
                            "land": o.get("land", account.get("land", "Deutschland")),
                            "zahlungsmittel": o.get("zahlungsmittel", "PayPal"),
                        }
                    loaded = True
            except Exception:
                pass

        if not loaded:
            # Fallback-In-Memory-Daten für Tests
            self._orders = {
                "ORD-1001": {
                    "order_id": "ORD-1001",
                    "customer_email": "kunde1@example.com",
                    "purchase_date": now - timedelta(days=5),
                    "account_id": "ACC-101",
                    "items": [
                        {"item_id": "ART-901", "name": "Ergonomischer Bürostuhl", "price": 199.99},
                        {"item_id": "ART-902", "name": "Schreibtischunterlage", "price": 50.00}
                    ],
                    "total_amount": 249.99,
                    "currency": "EUR",
                    "adresse": "Musterstraße 42, 10115 Berlin",
                    "land": "Deutschland",
                    "zahlungsmittel": "PayPal",
                },
                "ORD-1002": {
                    "order_id": "ORD-1002",
                    "customer_email": "kunde2@example.com",
                    "purchase_date": now - timedelta(days=20),
                    "account_id": "ACC-102",
                    "items": [
                        {"item_id": "ART-801", "name": "Kabellose Tastatur", "price": 69.50},
                        {"item_id": "ART-802", "name": "Mauspad XXL", "price": 20.00}
                    ],
                    "total_amount": 89.50,
                    "currency": "EUR",
                    "adresse": "Goetheallee 7, 80331 München",
                    "land": "Deutschland",
                    "zahlungsmittel": "Klarna",
                },
                "ORD-1003": {
                    "order_id": "ORD-1003",
                    "customer_email": "kunde3@example.com",
                    "purchase_date": now - timedelta(days=45),
                    "account_id": "ACC-103",
                    "items": [
                        {"item_id": "ART-701", "name": "4K Monitor 27 Zoll", "price": 420.00}
                    ],
                    "total_amount": 420.00,
                    "currency": "EUR",
                    "adresse": "Hauptstraße 15, 50667 Köln",
                    "land": "Deutschland",
                    "zahlungsmittel": "Kreditkarte",
                },
            }
            self._accounts = {
                "ACC-101": {
                    "account_id": "ACC-101",
                    "name": "Max",
                    "nachname": "Mustermann",
                    "email": "kunde1@example.com",
                    "telefonnummer": "+49 170 1234567",
                    "adresse": "Musterstraße 42, 10115 Berlin",
                    "land": "Deutschland",
                    "zahlungsmittel": "PayPal",
                    "password": "secret123"
                }
            }

    # ---------------------------------------------------------------------------
    # Account & Authentifizierung
    # ---------------------------------------------------------------------------
    def authenticate_account(self, login: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authentifiziert einen Account per E-Mail oder Account-ID und Passwort.
        Gibt die sicheren Profildaten zurück (ohne Passwort).
        """
        if not login or not password:
            return None

        clean_login = login.strip().lower()
        clean_pw = password.strip()

        for acc_id, acc in self._accounts.items():
            email_match = acc.get("email", "").strip().lower() == clean_login
            id_match = acc_id.strip().lower() == clean_login
            if (email_match or id_match) and acc.get("password") == clean_pw:
                # Kopie ohne Passwort zurückgeben
                safe_copy = dict(acc)
                safe_copy.pop("password", None)
                return safe_copy

        return None

    def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Gibt Account-Daten ohne Passwort zurück."""
        clean_id = (account_id or "").strip().upper()
        acc = self._accounts.get(clean_id)
        if not acc:
            for a in self._accounts.values():
                if a.get("account_id", "").upper() == clean_id:
                    acc = a
                    break
        if not acc:
            return None
        safe = dict(acc)
        safe.pop("password", None)
        return safe

    def update_account_data(self, account_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aktualisiert Profildaten (Name, Nachname, Adresse, Land, Telefonnummer).
        STRIKT GESPERRT: Anmeldedaten (email, account_id, password) sind unveränderlich!
        """
        acc = self._accounts.get(account_id)
        if not acc:
            for k, a in self._accounts.items():
                if a.get("account_id") == account_id:
                    acc = a
                    break
        if not acc:
            raise ValueError(f"Account {account_id} nicht gefunden.")

        # Sicherheitsprüfung: Anmeldedaten dürfen NIEMALS geändert werden
        forbidden_keys = {"email", "account_id", "password", "password_hash"}
        rejected_keys = [k for k in updates if k in forbidden_keys]
        if rejected_keys:
            raise ValueError(f"Anmeldedaten ({', '.join(rejected_keys)}) können aus Sicherheitsgründen nicht geändert werden.")

        allowed_keys = {"name", "nachname", "adresse", "land", "telefonnummer", "zahlungsmittel"}
        applied_changes = {}
        for k, v in updates.items():
            if k in allowed_keys and v is not None:
                acc[k] = str(v).strip()
                applied_changes[k] = acc[k]

        safe_acc = dict(acc)
        safe_acc.pop("password", None)
        return safe_acc

    def get_orders_for_account(self, account_id: str) -> List[Dict[str, Any]]:
        """Gibt alle Bestellungen eines Accounts zurück."""
        res = []
        for oid, o in self._orders.items():
            if o.get("account_id") == account_id:
                res.append(self.get_order_details(oid))
        return [r for r in res if r is not None]

    # ---------------------------------------------------------------------------
    # Bestellungen & Retouren (Abwärtskompatibel)
    # ---------------------------------------------------------------------------
    def verify_order(self, order_id: str, email: str) -> bool:
        """
        Prüft, ob die Kombination aus Bestellnummer und E-Mail-Adresse existiert.
        """
        if not order_id or not email:
            return False

        clean_order_id = order_id.strip().upper()
        clean_email = email.strip().lower()

        order = self._orders.get(clean_order_id)
        if not order:
            return False

        return order["customer_email"].strip().lower() == clean_email

    def get_order_details(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Gibt Bestelldaten inklusive Kaufdatum und berechneter Tage seit dem Kauf zurück.
        """
        clean_order_id = order_id.strip().upper() if order_id else ""
        order = self._orders.get(clean_order_id)
        if not order:
            return None

        now = datetime.now()
        days_since_purchase = (now - order["purchase_date"]).days

        return {
            "order_id": order["order_id"],
            "customer_email": order["customer_email"],
            "account_id": order.get("account_id"),
            "purchase_date": order["purchase_date"].strftime("%Y-%m-%d"),
            "days_since_purchase": days_since_purchase,
            "items": list(order["items"]),
            "total_amount": order["total_amount"],
            "currency": order["currency"],
            "adresse": order.get("adresse", ""),
            "land": order.get("land", "Deutschland"),
        }

    def book_return(
        self,
        order_id: str,
        return_type: str,
        returned_items: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Bucht eine Retoure im Mock-System für ausgewählte oder alle Artikel.
        Erzeugt eine fiktive Return-ID (RET-XXXX) und eine Label-Download-URL.
        """
        clean_order_id = order_id.strip().upper() if order_id else "UNKNOWN"
        return_code = uuid.uuid4().hex[:6].upper()
        return_id = f"RET-{return_code}"

        order = self.get_order_details(clean_order_id)
        all_items = order.get("items", []) if order else []

        if returned_items is None or len(returned_items) == 0:
            final_items = all_items
        else:
            final_items = returned_items

        total_refund = sum(
            float(it.get("price", it.get("preis", 0.0))) if isinstance(it, dict) else 99.0
            for it in final_items
        )

        booking = {
            "return_id": return_id,
            "order_id": clean_order_id,
            "return_type": return_type,  # 'refund' oder 'store_credit'
            "status": "CONFIRMED",
            "items": final_items,
            "total_refund": round(total_refund, 2),
            "label_url": f"/api/returns/{return_id}/label.pdf",
            "created_at": datetime.now().isoformat(),
        }
        self._returns[return_id] = booking
        return booking

    def get_return_booking(self, return_id: str) -> Optional[Dict[str, Any]]:
        """Gibt Buchungsdaten einer Retoure anhand der Return-ID zurück."""
        clean_id = (return_id or "").strip().upper()
        return self._returns.get(clean_id)


# Singleton für gemeinsame Nutzung
_global_repo: Optional[MockOrderRepository] = None

def get_repository() -> MockOrderRepository:
    global _global_repo
    if _global_repo is None:
        _global_repo = MockOrderRepository()
    return _global_repo


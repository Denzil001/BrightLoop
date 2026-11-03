from decimal import Decimal
import uuid
import pytest
from fastapi.testclient import TestClient


def test_tax_rule_crud_and_validation(client: TestClient, admin_auth, staff_auth, customer_auth):
    """Admin can create and update tax rules; 0-100% bound enforced; Staff reads; Customer forbidden."""
    admin_headers = {
        "Authorization": f"Bearer {admin_auth['token']}",
        "X-CSRF-Token": admin_auth["csrf_token"],
        "Origin": "http://localhost:3000",
    }
    # Create valid 18% GST tax rule
    create_payload = {
        "name": "Standard GST 18%",
        "classification": "GST",
        "rate": "18.0000",
        "active": True,
    }
    resp = client.post("/api/v1/taxes", json=create_payload, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    tax_data = resp.json()
    tax_id = tax_data["id"]
    assert tax_data["name"] == "Standard GST 18%"
    assert tax_data["rate"] == "18.0000"

    # Rate > 100 rejected
    bad_resp = client.post(
        "/api/v1/taxes",
        json={"name": "Excessive Tax", "classification": "VAT", "rate": "105.0000"},
        headers=admin_headers,
    )
    assert bad_resp.status_code == 422

    # Negative rate rejected
    bad_neg = client.post(
        "/api/v1/taxes",
        json={"name": "Negative Tax", "classification": "VAT", "rate": "-5.0000"},
        headers=admin_headers,
    )
    assert bad_neg.status_code == 422

    # Staff can read tax rules
    staff_headers = {"Authorization": f"Bearer {staff_auth['token']}"}
    staff_resp = client.get("/api/v1/taxes", headers=staff_headers)
    assert staff_resp.status_code == 200
    assert any(t["id"] == tax_id for t in staff_resp.json()["items"])

    # Customer forbidden
    cust_headers = {"Authorization": f"Bearer {customer_auth['token']}"}
    cust_resp = client.get("/api/v1/taxes", headers=cust_headers)
    assert cust_resp.status_code == 403

    # Admin updates tax rule
    up_resp = client.patch(
        f"/api/v1/taxes/{tax_id}",
        json={"rate": "12.0000"},
        headers=admin_headers,
    )
    assert up_resp.status_code == 200
    assert up_resp.json()["rate"] == "12.0000"

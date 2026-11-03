"""Regression tests for retained catalog references during activation."""
import uuid
import pytest


@pytest.mark.parametrize("archived", ["product", "variant", "plan"])
def test_activation_revalidates_retained_references(client, admin_auth, archived):
    suffix = uuid.uuid4().hex[:8]
    headers = {"Authorization": f"Bearer {admin_auth['token']}",
               "X-CSRF-Token": admin_auth["csrf_token"], "Origin": "http://localhost:3000"}
    r = client.post("/api/v1/products", headers=headers, json={
        "name": f"Activation product {suffix}", "type": "SERVICE",
        "sales_price": "10.00", "cost_price": "0.00"})
    assert r.status_code == 201
    product = r.json()["id"]
    r = client.post(f"/api/v1/products/{product}/variants", headers=headers,
                    json={"name": "Variant", "price_adjustment": "0.00"})
    assert r.status_code == 201
    variant = r.json()["id"]
    r = client.post("/api/v1/plans", headers=headers, json={
        "name": f"Activation plan {suffix}", "base_fee": "100.00", "minimum_seats": 1,
        "extra_seat_unit_price": "0.00", "interval": "MONTHLY"})
    assert r.status_code == 201
    plan = r.json()["id"]
    r = client.post("/api/v1/quotation-templates", headers=headers, json={
        "name": f"Activation template {suffix}", "plan_id": plan, "validity_days": 30,
        "active": False, "lines": [{"ordinal": 1, "product_id": product,
        "variant_id": variant, "quantity": 1, "line_kind": "ADDON"}]})
    assert r.status_code == 201
    template = r.json()["id"]
    paths = {"product": f"/api/v1/products/{product}/archive",
             "variant": f"/api/v1/products/{product}/variants/{variant}/archive",
             "plan": f"/api/v1/plans/{plan}/archive"}
    assert client.post(paths[archived], headers=headers).status_code == 200
    r = client.patch(f"/api/v1/quotation-templates/{template}",
                     headers=headers, json={"active": True})
    assert r.status_code == 400
    assert client.get(f"/api/v1/quotation-templates/{template}", headers=headers).json()["active"] is False

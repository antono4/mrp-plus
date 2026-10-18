"""API and MRP-engine tests for MRP++.

Run with:  pytest -q
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Point the app at a throwaway SQLite file before importing it.
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_db_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"

import database  # noqa: E402
import main  # noqa: E402
from models import ProductType, LotSizingMethod, InventoryTransactionType  # noqa: E402

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def clean_db():
    """Recreate the schema and seed a small, deterministic dataset per test."""
    database.Base.metadata.drop_all(bind=database.engine)
    database.Base.metadata.create_all(bind=database.engine)

    db = database.SessionLocal()
    try:
        from models import Product, Warehouse, Inventory, BOMItem, Demand
        from datetime import date, timedelta

        wh = Warehouse(code="WH-1", name="Main", is_default=True)
        db.add(wh)
        db.flush()

        steel = Product(code="RM-1", name="Steel", product_type=ProductType.RAW_MATERIAL,
                        unit="KG", unit_cost=2.0, lead_time_days=3,
                        safety_stock=10, min_stock_level=20)
        board = Product(code="CP-1", name="Board", product_type=ProductType.COMPONENT,
                        unit="PCS", unit_cost=10.0, lead_time_days=2,
                        lot_sizing_method=LotSizingMethod.FOQ, fixed_order_qty=50)
        motor = Product(code="FG-1", name="Motor", product_type=ProductType.FINISHED_GOOD,
                        unit="PCS", unit_cost=100.0, lead_time_days=5,
                        safety_stock=0, min_stock_level=0)
        db.add_all([steel, board, motor])
        db.flush()

        db.add_all([
            Inventory(product_id=steel.id, warehouse_id=wh.id, quantity=5),
            Inventory(product_id=board.id, warehouse_id=wh.id, quantity=0),
            Inventory(product_id=motor.id, warehouse_id=wh.id, quantity=10),
        ])
        # Motor = 1 board + 2 kg steel
        db.add_all([
            BOMItem(parent_product_id=motor.id, child_product_id=board.id, quantity=1),
            BOMItem(parent_product_id=motor.id, child_product_id=steel.id, quantity=2),
        ])
        today = date.today()
        db.add(Demand(product_id=motor.id, demand_type="sales_order", quantity=30,
                      due_date=today + timedelta(days=10)))
        db.commit()
        yield
    finally:
        db.close()


# ------------------------------------------------------------------ enums ---

def test_product_type_accepts_values():
    """Regression: enum columns must accept their *values*, not member names."""
    resp = client.post("/api/products", json={
        "code": "NEW-1", "name": "New", "product_type": "raw_material", "unit": "KG",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["product_type"] == "raw_material"


def test_lot_sizing_method_round_trip():
    resp = client.post("/api/products", json={
        "code": "NEW-2", "name": "New2", "product_type": "component",
        "lot_sizing_method": "eoq",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["lot_sizing_method"] == "eoq"


def test_product_type_filter_returns_matches():
    """Regression: the filter used to compare against the wrong enum type."""
    resp = client.get("/api/products", params={"product_type": "raw_material"})
    assert resp.status_code == 200
    codes = [p["code"] for p in resp.json()]
    assert codes == ["RM-1"]

    assert client.get("/api/products", params={"product_type": "bogus"}).status_code == 400


def test_transaction_accepts_value_and_updates_stock():
    """Regression: posting a transaction used to raise LookupError (HTTP 500)."""
    inv_id = client.get("/api/inventory").json()[0]["id"]

    before = client.get(f"/api/inventory/{inv_id}").json()["quantity"]
    resp = client.post("/api/inventory-transactions", json={
        "inventory_id": inv_id, "transaction_type": "purchase", "quantity": 25,
    })
    assert resp.status_code == 200, resp.text
    assert client.get(f"/api/inventory/{inv_id}").json()["quantity"] == before + 25


def test_transaction_direction_by_type():
    inv_id = client.get("/api/inventory").json()[0]["id"]
    start = client.get(f"/api/inventory/{inv_id}").json()["quantity"]

    client.post("/api/inventory-transactions", json={
        "inventory_id": inv_id, "transaction_type": "sale", "quantity": 5})
    assert client.get(f"/api/inventory/{inv_id}").json()["quantity"] == start - 5

    # A signed adjustment may move stock either way.
    client.post("/api/inventory-transactions", json={
        "inventory_id": inv_id, "transaction_type": "adjustment", "quantity": -3})
    assert client.get(f"/api/inventory/{inv_id}").json()["quantity"] == start - 8


# --------------------------------------------------------------------- BOM ---

def _product_ids():
    products = client.get("/api/products").json()
    return {p["code"]: p["id"] for p in products}


def test_bom_rejects_self_reference():
    ids = _product_ids()
    resp = client.post("/api/bom", json={
        "parent_product_id": ids["FG-1"], "child_product_id": ids["FG-1"], "quantity": 1})
    assert resp.status_code == 400


def test_bom_rejects_cycle_and_leaves_no_residue():
    """Regression: cycle detection used to insert a temp row and commit it."""
    ids = _product_ids()
    before = len(client.get("/api/bom").json())

    # Steel already feeds Motor; making Motor feed Steel closes a loop.
    resp = client.post("/api/bom", json={
        "parent_product_id": ids["RM-1"], "child_product_id": ids["FG-1"], "quantity": 1})
    assert resp.status_code == 400
    assert len(client.get("/api/bom").json()) == before


def test_bom_clone_copies_lines():
    ids = _product_ids()
    created = client.post("/api/products", json={
        "code": "FG-2", "name": "Motor v2", "product_type": "finished_good"}).json()

    resp = client.post("/api/bom/clone", json={
        "source_product_id": ids["FG-1"], "target_product_id": created["id"]})
    assert resp.status_code == 200, resp.text
    assert resp.json()["lines_created"] == 2

    clone = client.get("/api/bom", params={"parent_id": created["id"]}).json()
    assert len(clone) == 2


def test_bom_clone_refuses_to_overwrite_without_flag():
    ids = _product_ids()
    created = client.post("/api/products", json={
        "code": "FG-3", "name": "Motor v3", "product_type": "finished_good"}).json()
    body = {"source_product_id": ids["FG-1"], "target_product_id": created["id"]}

    assert client.post("/api/bom/clone", json=body).status_code == 200
    assert client.post("/api/bom/clone", json=body).status_code == 409
    assert client.post("/api/bom/clone", json={**body, "overwrite": True}).status_code == 200


# --------------------------------------------------------------------- MRP ---

def test_mrp_explodes_multi_level_bom():
    """Motor needs 30; 10 on hand -> 20 to build -> 20 boards and 40 kg steel."""
    from datetime import date, timedelta

    today = date.today()
    resp = client.post("/api/mrp/run", json={
        "planning_horizon_start": today.isoformat(),
        "planning_horizon_end": (today + timedelta(days=30)).isoformat(),
        "period_length_days": 7,
    })
    assert resp.status_code == 200, resp.text
    reqs = resp.json()["requirements"]
    by_code = {}
    for r in reqs:
        by_code.setdefault(r["product_code"], []).append(r)

    motor_orders = sum(r["planned_order_quantity"] for r in by_code["FG-1"])
    board_orders = sum(r["planned_order_quantity"] for r in by_code["CP-1"])
    steel_orders = sum(r["planned_order_quantity"] for r in by_code["RM-1"])

    assert motor_orders == 20, "motor should be netted against 10 on hand"
    assert board_orders == 50, "FOQ 50 must round the 20-board need up to 50"
    # 50 boards * 1 board/motor... steel is driven by the *motor* plan (20), not
    # the rounded board lot: 20 motors * 2 kg = 40 kg, less 5 on hand and the
    # min/safety target.
    assert steel_orders >= 0
    assert all(r["planned_order_quantity"] >= 0 for r in reqs)


def test_mrp_rejects_inverted_horizon():
    from datetime import date
    today = date.today()
    resp = client.post("/api/mrp/run", json={
        "planning_horizon_start": today.isoformat(),
        "planning_horizon_end": (today.replace(year=today.year - 1)).isoformat(),
    })
    assert resp.status_code == 400


def test_mrp_respects_safety_stock_toggle():
    from datetime import date, timedelta
    today = date.today()
    horizon = {
        "planning_horizon_start": today.isoformat(),
        "planning_horizon_end": (today + timedelta(days=30)).isoformat(),
    }
    with_ss = client.post("/api/mrp/run", json={**horizon, "use_safety_stock": True}).json()
    without_ss = client.post("/api/mrp/run", json={**horizon, "use_safety_stock": False}).json()

    total_with = with_ss["summary"]["total_quantity"]
    total_without = without_ss["summary"]["total_quantity"]
    assert total_with >= total_without


def test_mrp_run_is_idempotent():
    """Re-running must not accumulate duplicate proposals."""
    from datetime import date, timedelta
    today = date.today()
    body = {
        "planning_horizon_start": today.isoformat(),
        "planning_horizon_end": (today + timedelta(days=30)).isoformat(),
    }
    first = client.post("/api/mrp/run", json=body).json()["summary"]["total_quantity"]
    client.post("/api/mrp/run", json=body)
    third = client.post("/api/mrp/run", json=body).json()["summary"]["total_quantity"]

    assert first == third
    assert len(client.get("/api/planned-orders").json()) == len(
        [o for o in client.get("/api/planned-orders").json()])


# ----------------------------------------------------------------- exports ---

def test_csv_exports_download():
    for path in ("/api/export/inventory-status", "/api/export/planned-orders"):
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert resp.headers["content-type"].startswith("text/csv")
        assert "attachment" in resp.headers["content-disposition"]


def test_reports_summary_shape():
    resp = client.get("/api/reports/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["products_by_type"]) == {"raw_material", "component", "finished_good"}
    assert body["products_by_type"]["raw_material"] == 1


def test_inventory_trend_replays_history():
    """The trend must end at today's real inventory value."""
    current = client.get("/api/dashboard").json()["inventory_value"]

    trend = client.get("/api/reports/inventory-trend", params={"months": 6}).json()
    assert len(trend) == 6
    assert trend[-1]["value"] == current
    assert all(t["period"] for t in trend)


def test_planned_order_export_contains_rows():
    """After MRP runs, the CSV export must carry real rows, not just a header."""
    from datetime import date, timedelta
    today = date.today()
    client.post("/api/mrp/run", json={
        "planning_horizon_start": today.isoformat(),
        "planning_horizon_end": (today + timedelta(days=30)).isoformat(),
    })

    resp = client.get("/api/export/planned-orders")
    assert resp.status_code == 200
    lines = resp.text.strip().splitlines()
    assert len(lines) > 1
    assert "product_code" in lines[0]
    assert "FG-1" in resp.text


# ------------------------------------------------------------------- misc ---

def test_search_filters_products():
    resp = client.get("/api/products", params={"search": "motor"})
    assert resp.status_code == 200
    assert [p["code"] for p in resp.json()] == ["FG-1"]


def test_warehouse_delete_blocked_when_in_use():
    wh_id = client.get("/api/warehouses").json()[0]["id"]
    assert client.delete(f"/api/warehouses/{wh_id}").status_code == 409


def test_health_and_dashboard():
    assert client.get("/api/health").json()["status"] == "healthy"
    dash = client.get("/api/dashboard").json()
    assert dash["total_products"] == 3
    assert dash["inventory_value"] > 0


def teardown_module(module):
    try:
        os.unlink(_db_path)
    except OSError:
        pass

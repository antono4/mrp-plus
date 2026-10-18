"""MRP calculation engine for MRP++.

The engine is time-phased and multi-level:

1. Independent demand (sales orders, forecasts) is bucketed into planning periods.
2. Products are processed in low-level-code order, so a parent is always planned
   before its children.
3. Each planned order *release* creates dependent demand for the child items at
   the parent's release date, which is when the components are actually needed.
4. Every level is netted against on-hand stock, scheduled receipts, safety stock
   and minimum stock, then sized with the product's lot-sizing rule.
"""

from sqlalchemy.orm import Session
from models import Product, BOMItem, Inventory, Demand, PlannedOrder, MRPRun, Warehouse
from schemas import MRPParameters, MRPRequirement, MRPResult, DashboardSummary, StockAlert
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
import math

# Hard cap so a malformed BOM graph cannot spin the low-level-code pass forever.
_MAX_BOM_DEPTH = 20


class MRPEngine:
    """Material Requirements Planning calculation engine."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ BOM ---

    def get_product_bom(self, product_id: int, as_of_date: date = None) -> List[Dict]:
        """Get the effective BOM lines for a product."""
        if as_of_date is None:
            as_of_date = date.today()

        items = self.db.query(BOMItem).filter(
            BOMItem.parent_product_id == product_id,
            (BOMItem.effective_from == None) | (BOMItem.effective_from <= as_of_date),
            (BOMItem.effective_to == None) | (BOMItem.effective_to >= as_of_date),
        ).all()

        return [
            {
                "id": item.id,
                "child_product_id": item.child_product_id,
                "quantity": item.quantity,
                "is_optional": item.is_optional,
                "scrap_percentage": item.scrap_percentage or 0.0,
            }
            for item in items
        ]

    def _bom_edges(self, as_of_date: date = None) -> List[tuple]:
        """Return (parent_id, child_id, quantity, scrap_pct) for effective lines."""
        if as_of_date is None:
            as_of_date = date.today()

        rows = self.db.query(BOMItem).filter(
            (BOMItem.effective_from == None) | (BOMItem.effective_from <= as_of_date),
            (BOMItem.effective_to == None) | (BOMItem.effective_to >= as_of_date),
        ).all()

        return [
            (r.parent_product_id, r.child_product_id, r.quantity, r.scrap_percentage or 0.0)
            for r in rows
        ]

    def low_level_codes(self, product_ids: List[int], as_of_date: date = None) -> Dict[int, int]:
        """Compute the low-level code of each product (0 = no parent)."""
        codes = {pid: 0 for pid in product_ids}
        edges = self._bom_edges(as_of_date)

        for _ in range(_MAX_BOM_DEPTH):
            changed = False
            for parent_id, child_id, _, _ in edges:
                if parent_id in codes and child_id in codes:
                    candidate = codes[parent_id] + 1
                    if codes[child_id] < candidate:
                        codes[child_id] = candidate
                        changed = True
            if not changed:
                break

        return codes

    def check_circular_bom(self, product_id: int, visited: set = None) -> bool:
        """Return True if the BOM reachable from ``product_id`` contains a cycle."""
        if visited is None:
            visited = set()

        if product_id in visited:
            return True

        visited = visited | {product_id}

        for item in self.get_product_bom(product_id):
            if self.check_circular_bom(item["child_product_id"], visited):
                return True

        return False

    # -------------------------------------------------------------- inventory ---

    def get_available_stock(self, product_id: int, warehouse_id: int = None) -> float:
        """Available (unreserved) stock, summed across warehouses when none given."""
        query = self.db.query(Inventory).filter(Inventory.product_id == product_id)
        if warehouse_id:
            query = query.filter(Inventory.warehouse_id == warehouse_id)

        return float(sum(max(0.0, inv.quantity - inv.reserved_quantity) for inv in query.all()))

    # --------------------------------------------------------------- planning ---

    def _bucket_index(self, day: date, start: date, period_days: int) -> int:
        return max(0, (day - start).days // period_days)

    def _bucket_date(self, index: int, start: date, period_days: int) -> date:
        return start + timedelta(days=index * period_days)

    def get_demand_forecast(self, product_id: int, start_date: date, end_date: date) -> Dict[str, float]:
        """Aggregate open demand for a product by due date."""
        demands = self.db.query(Demand).filter(
            Demand.product_id == product_id,
            Demand.due_date >= start_date,
            Demand.due_date <= end_date,
            Demand.is_fulfilled == False,
        ).all()

        forecast: Dict[str, float] = {}
        for demand in demands:
            key = demand.due_date.isoformat()
            forecast[key] = forecast.get(key, 0.0) + demand.quantity
        return forecast

    def get_scheduled_receipts(self, product_id: int, start_date: date,
                               end_date: date) -> Dict[str, float]:
        """Scheduled receipts already on the books for a product."""
        orders = self.db.query(PlannedOrder).filter(
            PlannedOrder.product_id == product_id,
            PlannedOrder.start_date >= start_date - timedelta(days=365),
            PlannedOrder.start_date <= end_date,
            PlannedOrder.status.in_(["released", "firm"]),
        ).all()

        receipts: Dict[str, float] = {}
        for order in orders:
            key = order.start_date.isoformat()
            receipts[key] = receipts.get(key, 0.0) + order.quantity
        return receipts

    # ------------------------------------------------------------- lot sizing ---

    def calculate_eoq(self, product: Product, annual_demand: float = 1000) -> float:
        """Economic order quantity: sqrt(2 * annual demand * order cost / holding cost)."""
        if product.unit_cost <= 0 or annual_demand <= 0:
            return product.fixed_order_qty if product.fixed_order_qty > 0 else 100.0

        ordering_cost = 25.0
        holding_cost_rate = 0.20
        holding_cost = product.unit_cost * holding_cost_rate

        if holding_cost <= 0:
            return product.fixed_order_qty if product.fixed_order_qty > 0 else annual_demand

        eoq = math.sqrt((2 * annual_demand * ordering_cost) / holding_cost)
        return round(eoq, 2)

    def apply_lot_sizing(self, product: Product, net_requirement: float,
                         annual_demand: float = None) -> float:
        """Apply the product's lot-sizing rule to a net requirement."""
        if net_requirement <= 0:
            return 0.0

        method = product.lot_sizing_method
        method = method.value if hasattr(method, "value") else str(method)

        if method == "foq":
            fixed = product.fixed_order_qty or 0.0
            if fixed <= 0:
                return net_requirement
            # Fixed order quantity: order whole multiples so the lot covers the need.
            return math.ceil(net_requirement / fixed) * fixed

        if method == "eoq":
            eoq = self.calculate_eoq(product, annual_demand or net_requirement * 12)
            if eoq <= 0:
                return net_requirement
            return math.ceil(net_requirement / eoq) * eoq

        if method == "poq":
            # Period order quantity: cover a fixed number of future periods.
            periods = max(1, product.fixed_order_qty or 4)
            return net_requirement * periods

        return net_requirement  # LFL and anything unrecognised

    # ------------------------------------------------------------------- run ---

    def run_mrp(self, params: MRPParameters) -> MRPResult:
        """Run a full multi-level, time-phased MRP calculation."""
        period_days = max(1, getattr(params, "period_length_days", 7) or 7)
        start = params.planning_horizon_start
        end = params.planning_horizon_end

        if end < start:
            raise ValueError("planning_horizon_end must not be before planning_horizon_start")

        mrp_run = MRPRun(
            planning_horizon_start=start,
            planning_horizon_end=end,
            status="completed",
            notes=f"period_length_days={period_days}",
        )
        self.db.add(mrp_run)
        self.db.commit()
        self.db.refresh(mrp_run)

        # Drop only proposals from earlier runs; released orders are kept.
        self.db.query(PlannedOrder).filter(
            PlannedOrder.status == "proposed",
            PlannedOrder.start_date >= start - timedelta(days=365),
            PlannedOrder.end_date <= end,
        ).delete(synchronize_session=False)
        self.db.commit()

        products = self.db.query(Product).filter(Product.is_active == True).all()
        by_id = {p.id: p for p in products}
        if not products:
            return MRPResult(
                run_id=mrp_run.id, run_date=mrp_run.run_date,
                planning_horizon_start=start, planning_horizon_end=end,
                requirements=[], summary=self._empty_summary(),
            )

        # Independent demand per product, bucketed.
        gross: Dict[int, Dict[int, float]] = {p.id: {} for p in products}
        for demand in self.db.query(Demand).filter(
            Demand.due_date >= start, Demand.due_date <= end,
            Demand.is_fulfilled == False,
        ).all():
            if demand.product_id not in gross:
                continue
            idx = self._bucket_index(demand.due_date, start, period_days)
            gross[demand.product_id][idx] = gross[demand.product_id].get(idx, 0.0) + demand.quantity

        # Bucketed scheduled receipts for every product.
        receipts: Dict[int, Dict[int, float]] = {p.id: {} for p in products}
        for order in self.db.query(PlannedOrder).filter(
            PlannedOrder.status.in_(["released", "firm"]),
            PlannedOrder.start_date >= start - timedelta(days=365),
            PlannedOrder.start_date <= end,
        ).all():
            if order.product_id not in receipts:
                continue
            idx = self._bucket_index(order.start_date, start, period_days)
            receipts[order.product_id][idx] = receipts[order.product_id].get(idx, 0.0) + order.quantity

        codes = self.low_level_codes(list(by_id.keys()), start)
        ordered = sorted(by_id.values(), key=lambda p: (codes.get(p.id, 0), p.code))

        requirements: List[MRPRequirement] = []
        summary = self._empty_summary()
        edges = self._bom_edges(start)

        for product in ordered:
            self._plan_product(
                product, codes, edges, gross, receipts, requirements, summary,
                start, end, period_days, params,
            )

        self.db.commit()

        return MRPResult(
            run_id=mrp_run.id,
            run_date=mrp_run.run_date,
            planning_horizon_start=start,
            planning_horizon_end=end,
            requirements=requirements,
            summary=summary,
        )

    def _empty_summary(self) -> Dict:
        return {
            "total_products_planned": 0,
            "total_orders_proposed": 0,
            "total_quantity": 0.0,
            "total_shortages": 0,
            "total_order_value": 0.0,
        }

    def _plan_product(self, product, codes, edges, gross, receipts, requirements,
                      summary, start, end, period_days, params) -> None:
        """Net one product across the horizon and push demand to its children."""
        periods = (end - start).days // period_days + 1
        on_hand = self.get_available_stock(product.id)
        target = 0.0
        if getattr(params, "use_safety_stock", True):
            target = max(target, product.safety_stock or 0.0)
        if getattr(params, "use_min_stock_level", True):
            target = max(target, product.min_stock_level or 0.0)

        product_gross = gross.setdefault(product.id, {})
        product_receipts = receipts.setdefault(product.id, {})
        produced = 0

        annual_demand = sum(product_gross.values()) * (365.0 / max(1, (end - start).days))

        for idx in range(periods):
            bucket_date = self._bucket_date(idx, start, period_days)
            gross_qty = product_gross.get(idx, 0.0)
            sched_qty = product_receipts.get(idx, 0.0)

            projected = on_hand + sched_qty
            net_req = max(0.0, gross_qty + target - projected)

            order_qty = 0.0
            release_date = None
            action_msg = None

            if net_req > 0:
                order_qty = self.apply_lot_sizing(product, net_req, annual_demand)
                release_date = bucket_date - timedelta(days=product.lead_time_days or 0)

                order_type = ("purchase"
                              if getattr(product.product_type, "value", None) == "raw_material"
                              else "production")

                if release_date <= date.today():
                    action_msg = f"URGENT: release {order_qty:.2f} {product.unit} now (past due)"
                    summary["total_shortages"] += 1
                else:
                    action_msg = f"Order {order_qty:.2f} {product.unit} by {release_date.isoformat()}"

                self.db.add(PlannedOrder(
                    product_id=product.id,
                    order_type=order_type,
                    quantity=order_qty,
                    start_date=release_date,
                    end_date=bucket_date,
                    status="proposed",
                    priority=1 if codes.get(product.id, 0) == 0 else 2,
                    action_message=action_msg,
                ))
                summary["total_orders_proposed"] += 1
                summary["total_quantity"] += order_qty
                summary["total_order_value"] += order_qty * (product.unit_cost or 0.0)

                # Push dependent demand to children at the release date.
                release_idx = self._bucket_index(release_date, start, period_days)
                for parent_id, child_id, qty_per, scrap in edges:
                    if parent_id != product.id or child_id not in gross:
                        continue
                    child_qty = order_qty * qty_per * (1 + scrap / 100.0)
                    bucket = gross[child_id]
                    bucket[release_idx] = bucket.get(release_idx, 0.0) + child_qty

                projected += order_qty
                produced += 1

            requirements.append(MRPRequirement(
                product_id=product.id,
                product_code=product.code,
                product_name=product.name,
                period=bucket_date.isoformat(),
                gross_requirement=gross_qty,
                scheduled_receipts=sched_qty,
                projected_on_hand=projected,
                net_requirement=net_req,
                planned_order_quantity=order_qty,
                planned_order_date=release_date,
                action_message=action_msg,
            ))

            on_hand = projected - gross_qty

        if produced:
            summary["total_products_planned"] += 1

    # --------------------------------------------------------------- reports ---

    def get_dashboard_summary(self) -> DashboardSummary:
        """Get dashboard summary statistics."""
        total_products = self.db.query(Product).filter(Product.is_active == True).count()
        total_demands = self.db.query(Demand).filter(
            Demand.due_date >= date.today(),
            Demand.is_fulfilled == False,
        ).count()
        pending_orders = self.db.query(PlannedOrder).filter(
            PlannedOrder.status.in_(["proposed", "released"])
        ).count()

        low_stock_count = 0
        inventory_value = 0.0

        for inv in self.db.query(Inventory).all():
            if inv.product and inv.product.is_active:
                available = inv.quantity - inv.reserved_quantity
                if available < self._alert_threshold(inv):
                    low_stock_count += 1
                inventory_value += available * (inv.product.unit_cost or 0)

        return DashboardSummary(
            total_products=total_products,
            total_demands=total_demands,
            pending_orders=pending_orders,
            low_stock_items=low_stock_count,
            inventory_value=round(inventory_value, 2),
        )

    @staticmethod
    def _alert_threshold(inv: Inventory) -> float:
        """Stock is low when it falls below either the product minimum or the
        warehouse reorder point, whichever is higher."""
        return max(inv.product.min_stock_level or 0.0, inv.reorder_point or 0.0)

    def get_stock_alerts(self) -> List[StockAlert]:
        """Get list of stock alerts."""
        alerts = []

        records = self.db.query(Inventory).join(Product).join(Warehouse).filter(
            Product.is_active == True
        ).all()

        for inv in records:
            available = inv.quantity - inv.reserved_quantity
            threshold = self._alert_threshold(inv)
            if available < threshold:
                alerts.append(StockAlert(
                    product_id=inv.product_id,
                    product_code=inv.product.code,
                    product_name=inv.product.name,
                    current_stock=available,
                    min_stock_level=threshold,
                    warehouse_name=inv.warehouse.name if inv.warehouse else "Unknown",
                ))

        return alerts


def validate_bom_circular_reference(db: Session, parent_id: int, child_id: int) -> bool:
    """Return True when adding parent -> child would introduce a BOM cycle.

    The candidate edge is checked in memory: a cycle exists exactly when the
    proposed child can already reach the proposed parent through existing
    edges. Nothing is written to the database, so a failed request cannot leak
    a temporary row.
    """
    if parent_id == child_id:
        return True

    edges: Dict[int, List[int]] = {}
    for parent, child in db.query(BOMItem.parent_product_id, BOMItem.child_product_id).all():
        edges.setdefault(parent, []).append(child)

    stack = [child_id]
    visited = set()
    while stack:
        node = stack.pop()
        if node == parent_id:
            return True
        if node in visited:
            continue
        visited.add(node)
        stack.extend(edges.get(node, ()))

    return False

"""MRP Calculation Engine for MRP++."""

from sqlalchemy.orm import Session
from sqlalchemy import and_
from models import Product, BOMItem, Inventory, Demand, PlannedOrder, MRPRun, Warehouse
from schemas import MRPParameters, MRPRequirement, MRPResult, DashboardSummary, StockAlert
from datetime import date, datetime, timedelta
from typing import List, Dict, Tuple, Optional
import math


class MRPEngine:
    """Material Requirements Planning calculation engine."""

    def __init__(self, db: Session):
        self.db = db

    def get_product_bom(self, product_id: int, as_of_date: date = None) -> List[Dict]:
        """Get BOM items for a product."""
        if as_of_date is None:
            as_of_date = date.today()

        items = self.db.query(BOMItem).filter(
            BOMItem.parent_product_id == product_id,
            (BOMItem.effective_from == None) | (BOMItem.effective_from <= as_of_date),
            (BOMItem.effective_to == None) | (BOMItem.effective_to >= as_of_date)
        ).all()

        return [
            {
                "id": item.id,
                "child_product_id": item.child_product_id,
                "quantity": item.quantity,
                "is_optional": item.is_optional,
                "scrap_percentage": item.scrap_percentage
            }
            for item in items
        ]

    def get_available_stock(self, product_id: int, warehouse_id: int = None) -> float:
        """Get available stock for a product."""
        query = self.db.query(Inventory).filter(Inventory.product_id == product_id)
        
        if warehouse_id:
            query = query.filter(Inventory.warehouse_id == warehouse_id)
        
        inventory = query.first()
        
        if inventory:
            return max(0, inventory.quantity - inventory.reserved_quantity)
        return 0.0

    def get_scheduled_receipts(self, product_id: int, start_date: date, end_date: date) -> Dict[str, float]:
        """Get scheduled receipts (planned orders) for a product within date range."""
        orders = self.db.query(PlannedOrder).filter(
            PlannedOrder.product_id == product_id,
            PlannedOrder.start_date >= start_date,
            PlannedOrder.start_date <= end_date,
            PlannedOrder.status.in_(["proposed", "released"])
        ).all()

        receipts = {}
        for order in orders:
            period_key = order.start_date.isoformat()
            receipts[period_key] = receipts.get(period_key, 0) + order.quantity
        
        return receipts

    def get_demand_forecast(self, product_id: int, start_date: date, end_date: date) -> Dict[str, float]:
        """Get aggregated demand for a product within date range."""
        demands = self.db.query(Demand).filter(
            Demand.product_id == product_id,
            Demand.due_date >= start_date,
            Demand.due_date <= end_date
        ).all()

        demand_forecast = {}
        for demand in demands:
            period_key = demand.due_date.isoformat()
            demand_forecast[period_key] = demand_forecast.get(period_key, 0) + demand.quantity
        
        return demand_forecast

    def calculate_gross_requirements(self, product_id: int, start_date: date, end_date: date) -> Dict[str, float]:
        """Calculate gross requirements through BOM explosion."""
        # Get independent demand (sales orders, forecasts)
        gross_req = self.get_demand_forecast(product_id, start_date, end_date)
        
        # Check if this is a manufactured product (has BOM)
        bom_items = self.get_product_bom(product_id)
        
        if bom_items:
            # For manufactured products, requirements come from parent products
            # This is handled recursively in the full MRP run
            pass
        
        return gross_req

    def calculate_eoq(self, product: Product, annual_demand: float = 1000) -> float:
        """Calculate Economic Order Quantity."""
        if product.unit_cost <= 0 or annual_demand <= 0:
            return product.fixed_order_qty if product.fixed_order_qty > 0 else 100
        
        # EOQ = sqrt(2 * D * S / H)
        # D = annual demand, S = ordering cost (assume $25), H = holding cost (assume 20% of unit cost)
        ordering_cost = 25.0
        holding_cost_rate = 0.20
        
        d = annual_demand
        s = ordering_cost
        h = product.unit_cost * holding_cost_rate
        
        eoq = math.sqrt((2 * d * s) / h) if h > 0 else product.fixed_order_qty
        return round(eoq, 2)

    def apply_lot_sizing(self, product: Product, net_requirement: float) -> float:
        """Apply lot sizing method to determine order quantity."""
        if net_requirement <= 0:
            return 0.0

        method = product.lot_sizing_method.value if hasattr(product.lot_sizing_method, 'value') else str(product.lot_sizing_method)
        
        if method == "lfl":
            # Lot for Lot - order exactly what's needed
            return net_requirement
        elif method == "foq":
            # Fixed Order Quantity
            return product.fixed_order_qty if product.fixed_order_qty > 0 else net_requirement
        elif method == "eoq":
            # Economic Order Quantity
            return self.calculate_eoq(product, net_requirement * 12)  # Assume monthly demand
        elif method == "poq":
            # Period Order Quantity - round up to cover requirements
            periods = 4  # Cover 4 periods at a time
            return net_requirement * periods
        else:
            return net_requirement

    def check_circular_bom(self, product_id: int, visited: set = None) -> bool:
        """Check if BOM has circular references."""
        if visited is None:
            visited = set()
        
        if product_id in visited:
            return True
        
        visited.add(product_id)
        
        bom_items = self.get_product_bom(product_id)
        for item in bom_items:
            if self.check_circular_bom(item["child_product_id"], visited.copy()):
                return True
        
        return False

    def mrp_explosion(self, product_id: int, quantity_needed: float, start_date: date, 
                      end_date: date, depth: int = 0) -> Dict[int, Dict[str, float]]:
        """
        Explode BOM to calculate requirements for all sub-components.
        Returns dictionary of {product_id: {date: quantity}}
        """
        if depth > 5:  # Max recursion depth
            return {}
        
        if self.check_circular_bom(product_id):
            return {}

        requirements = {}
        bom_items = self.get_product_bom(product_id)
        
        for item in bom_items:
            child_id = item["child_product_id"]
            qty_per = item["quantity"]
            scrap = item["scrap_percentage"]
            
            # Account for scrap
            adjusted_qty = quantity_needed * qty_per * (1 + scrap / 100)
            
            # Store the gross requirement
            if child_id not in requirements:
                requirements[child_id] = {}
            requirements[child_id][start_date.isoformat()] = \
                requirements[child_id].get(start_date.isoformat(), 0) + adjusted_qty
            
            # Recursively explode for this child's BOM
            child_reqs = self.mrp_explosion(child_id, adjusted_qty, start_date, end_date, depth + 1)
            
            # Merge child requirements
            for cid, date_qty in child_reqs.items():
                if cid not in requirements:
                    requirements[cid] = {}
                for d, q in date_qty.items():
                    requirements[cid][d] = requirements[cid].get(d, 0) + q
        
        return requirements

    def run_mrp(self, params: MRPParameters) -> MRPResult:
        """Run full MRP calculation."""
        # Create MRP run record
        mrp_run = MRPRun(
            planning_horizon_start=params.planning_horizon_start,
            planning_horizon_end=params.planning_horizon_end,
            status="completed"
        )
        self.db.add(mrp_run)
        self.db.commit()
        self.db.refresh(mrp_run)

        # Clear previous planned orders for this run
        self.db.query(PlannedOrder).filter(
            PlannedOrder.start_date >= params.planning_horizon_start,
            PlannedOrder.start_date <= params.planning_horizon_end
        ).delete()

        all_requirements = []
        summary = {
            "total_products_planned": 0,
            "total_orders_proposed": 0,
            "total_quantity": 0
        }

        # Get all products that have demand in the planning horizon
        products_with_demand = self.db.query(Demand.product_id).filter(
            Demand.due_date >= params.planning_horizon_start,
            Demand.due_date <= params.planning_horizon_end
        ).distinct().all()

        for (product_id,) in products_with_demand:
            product = self.db.query(Product).get(product_id)
            if not product or not product.is_active:
                continue

            # Get demand for this product
            demand_forecast = self.get_demand_forecast(product_id, 
                                                        params.planning_horizon_start, 
                                                        params.planning_horizon_end)

            # Calculate gross requirements from demand
            gross_req = demand_forecast

            # Get scheduled receipts
            scheduled_receipts = self.get_scheduled_receipts(product_id,
                                                               params.planning_horizon_start,
                                                               params.planning_horizon_end)

            # Get current available stock
            available_stock = self.get_available_stock(product_id)

            # Process each period
            current_stock = available_stock
            
            for period_str, gross_qty in sorted(gross_req.items()):
                period_date = date.fromisoformat(period_str)
                
                # Get scheduled receipts for this period
                sched_qty = scheduled_receipts.get(period_str, 0)
                
                # Project on-hand after receipts
                projected_on_hand = current_stock + sched_qty
                
                # Calculate net requirement
                net_req = max(0, gross_qty - projected_on_hand)
                
                # Apply safety stock
                if params.use_safety_stock:
                    net_req = max(0, net_req - product.safety_stock)
                
                # Apply lot sizing
                order_qty = self.apply_lot_sizing(product, net_req)
                
                # Determine planned order date (accounting for lead time)
                planned_date = period_date - timedelta(days=product.lead_time_days)
                
                # Generate action message
                action_msg = None
                if order_qty > 0:
                    action_msg = f"Order {order_qty:.0f} {product.unit}"
                    if available_stock < gross_qty:
                        action_msg = f"URGENT: {action_msg} - Stock shortage"
                    
                    # Create planned order
                    planned_order = PlannedOrder(
                        product_id=product_id,
                        order_type="purchase" if product.product_type.value == "raw_material" else "production",
                        quantity=order_qty,
                        start_date=planned_date,
                        end_date=period_date,
                        status="proposed",
                        priority=1,
                        action_message=action_msg
                    )
                    self.db.add(planned_order)
                    summary["total_orders_proposed"] += 1
                    summary["total_quantity"] += order_qty

                # Create MRP requirement record
                requirement = MRPRequirement(
                    product_id=product_id,
                    product_code=product.code,
                    product_name=product.name,
                    period=period_str,
                    gross_requirement=gross_qty,
                    scheduled_receipts=sched_qty,
                    projected_on_hand=projected_on_hand,
                    net_requirement=net_req,
                    planned_order_quantity=order_qty,
                    planned_order_date=planned_date if order_qty > 0 else None,
                    action_message=action_msg
                )
                all_requirements.append(requirement)
                
                # Update running stock
                current_stock = projected_on_hand - gross_qty

            # BOM explosion for manufactured products
            if product.product_type.value == "finished_good" and gross_req:
                total_demand = sum(gross_req.values())
                exploded = self.mrp_explosion(product_id, total_demand,
                                              params.planning_horizon_start,
                                              params.planning_horizon_end)
                
                for child_id, date_quantities in exploded.items():
                    child_product = self.db.query(Product).get(child_id)
                    if not child_product:
                        continue
                    
                    for date_str, qty in date_quantities.items():
                        period_date = date.fromisoformat(date_str)
                        
                        # Get existing planned orders for child
                        child_available = self.get_available_stock(child_id)
                        child_sched = self.get_scheduled_receipts(child_id,
                                                                    params.planning_horizon_start,
                                                                    params.planning_horizon_end)
                        
                        sched_qty = child_sched.get(date_str, 0)
                        projected = child_available + sched_qty
                        net_req = max(0, qty - projected)
                        
                        order_qty = self.apply_lot_sizing(child_product, net_req)
                        planned_date = period_date - timedelta(days=child_product.lead_time_days)
                        
                        if order_qty > 0:
                            action_msg = f"Order {order_qty:.0f} {child_product.unit}"
                            
                            planned_order = PlannedOrder(
                                product_id=child_id,
                                order_type="purchase",
                                quantity=order_qty,
                                start_date=planned_date,
                                end_date=period_date,
                                status="proposed",
                                priority=2,
                                action_message=action_msg
                            )
                            self.db.add(planned_order)
                            summary["total_orders_proposed"] += 1
                            summary["total_quantity"] += order_qty

            summary["total_products_planned"] += 1

        self.db.commit()

        return MRPResult(
            run_id=mrp_run.id,
            run_date=mrp_run.run_date,
            planning_horizon_start=params.planning_horizon_start,
            planning_horizon_end=params.planning_horizon_end,
            requirements=all_requirements,
            summary=summary
        )

    def get_dashboard_summary(self) -> DashboardSummary:
        """Get dashboard summary statistics."""
        total_products = self.db.query(Product).filter(Product.is_active == True).count()
        total_demands = self.db.query(Demand).filter(
            Demand.due_date >= date.today(),
            Demand.is_fulfilled == False
        ).count()
        pending_orders = self.db.query(PlannedOrder).filter(
            PlannedOrder.status.in_(["proposed", "released"])
        ).count()

        # Count low stock items
        low_stock_count = 0
        inventory_value = 0.0
        
        inventory_records = self.db.query(Inventory).all()
        for inv in inventory_records:
            if inv.product and inv.product.is_active:
                available = inv.quantity - inv.reserved_quantity
                if available < inv.product.min_stock_level:
                    low_stock_count += 1
                inventory_value += available * (inv.product.unit_cost or 0)

        return DashboardSummary(
            total_products=total_products,
            total_demands=total_demands,
            pending_orders=pending_orders,
            low_stock_items=low_stock_count,
            inventory_value=round(inventory_value, 2)
        )

    def get_stock_alerts(self) -> List[StockAlert]:
        """Get list of stock alerts."""
        alerts = []
        
        inventory_records = self.db.query(Inventory).join(Product).join(Warehouse).filter(
            Product.is_active == True
        ).all()
        
        for inv in inventory_records:
            available = inv.quantity - inv.reserved_quantity
            if available < inv.product.min_stock_level:
                alerts.append(StockAlert(
                    product_id=inv.product_id,
                    product_code=inv.product.code,
                    product_name=inv.product.name,
                    current_stock=available,
                    min_stock_level=inv.product.min_stock_level,
                    warehouse_name=inv.warehouse.name if inv.warehouse else "Unknown"
                ))
        
        return alerts


def validate_bom_circular_reference(db: Session, parent_id: int, child_id: int) -> bool:
    """Validate that adding a BOM item won't create circular reference."""
    engine = MRPEngine(db)
    
    # Temporarily add the BOM item to check
    temp_item = BOMItem(parent_product_id=parent_id, child_product_id=child_id, quantity=1)
    db.add(temp_item)
    db.commit()
    
    has_circular = engine.check_circular_bom(parent_id)
    
    # Remove temp item
    db.delete(temp_item)
    db.commit()
    
    return has_circular

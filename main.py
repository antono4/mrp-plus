"""MRP++ FastAPI Application."""

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime, timedelta
import os

from database import get_db, init_db, engine
from models import Product, BOMItem, Warehouse, Inventory, InventoryTransaction, Demand, PlannedOrder, ProductType, InventoryTransactionType
from schemas import (
    ProductCreate, ProductUpdate, ProductResponse,
    BOMItemCreate, BOMItemUpdate, BOMItemResponse,
    WarehouseCreate, WarehouseUpdate, WarehouseResponse,
    InventoryCreate, InventoryUpdate, InventoryResponse,
    InventoryTransactionCreate, InventoryTransactionResponse,
    DemandCreate, DemandUpdate, DemandResponse,
    PlannedOrderCreate, PlannedOrderUpdate, PlannedOrderResponse,
    MRPParameters, MRPResult, DashboardSummary, StockAlert
)
from mrp_engine import MRPEngine, validate_bom_circular_reference

app = FastAPI(
    title="MRP++",
    description="Material Requirements Planning Plus - Advanced Manufacturing Planning System",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
init_db()

# Serve static files
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


# Health check
@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "MRP++", "version": "1.0.0"}


# ==================== Dashboard ====================

@app.get("/api/dashboard", response_model=DashboardSummary)
def get_dashboard(db: Session = Depends(get_db)):
    """Get dashboard summary statistics."""
    engine = MRPEngine(db)
    return engine.get_dashboard_summary()


@app.get("/api/dashboard/alerts", response_model=List[StockAlert])
def get_stock_alerts(db: Session = Depends(get_db)):
    """Get stock alerts."""
    engine = MRPEngine(db)
    return engine.get_stock_alerts()


# ==================== Products ====================

@app.get("/api/products", response_model=List[ProductResponse])
def list_products(
    skip: int = 0,
    limit: int = 100,
    product_type: Optional[str] = None,
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db)
):
    """List all products."""
    query = db.query(Product)
    
    if product_type:
        query = query.filter(Product.product_type == product_type)
    if is_active is not None:
        query = query.filter(Product.is_active == is_active)
    
    return query.offset(skip).limit(limit).all()


@app.get("/api/products/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    """Get a specific product."""
    product = db.query(Product).get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@app.post("/api/products", response_model=ProductResponse)
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    """Create a new product."""
    # Check if code already exists
    existing = db.query(Product).filter(Product.code == product.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Product code already exists")
    
    db_product = Product(**product.model_dump())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


@app.put("/api/products/{product_id}", response_model=ProductResponse)
def update_product(product_id: int, product: ProductUpdate, db: Session = Depends(get_db)):
    """Update a product."""
    db_product = db.query(Product).get(product_id)
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    update_data = product.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_product, key, value)
    
    db.commit()
    db.refresh(db_product)
    return db_product


@app.delete("/api/products/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    """Delete a product (soft delete)."""
    db_product = db.query(Product).get(product_id)
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    db_product.is_active = False
    db.commit()
    return {"message": "Product deleted successfully"}


# ==================== Bill of Materials ====================

@app.get("/api/bom", response_model=List[BOMItemResponse])
def list_bom_items(
    parent_id: Optional[int] = None,
    child_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """List BOM items with optional filters."""
    query = db.query(BOMItem)
    
    if parent_id:
        query = query.filter(BOMItem.parent_product_id == parent_id)
    if child_id:
        query = query.filter(BOMItem.child_product_id == child_id)
    
    return query.all()


@app.get("/api/bom/{bom_id}", response_model=BOMItemResponse)
def get_bom_item(bom_id: int, db: Session = Depends(get_db)):
    """Get a specific BOM item."""
    bom_item = db.query(BOMItem).get(bom_id)
    if not bom_item:
        raise HTTPException(status_code=404, detail="BOM item not found")
    return bom_item


@app.post("/api/bom", response_model=BOMItemResponse)
def create_bom_item(bom_item: BOMItemCreate, db: Session = Depends(get_db)):
    """Create a new BOM item."""
    # Validate products exist
    parent = db.query(Product).get(bom_item.parent_product_id)
    child = db.query(Product).get(bom_item.child_product_id)
    
    if not parent or not child:
        raise HTTPException(status_code=400, detail="Parent or child product not found")
    
    # Check for circular reference
    if validate_bom_circular_reference(db, bom_item.parent_product_id, bom_item.child_product_id):
        raise HTTPException(status_code=400, detail="Circular BOM reference detected")
    
    db_bom = BOMItem(**bom_item.model_dump())
    db.add(db_bom)
    db.commit()
    db.refresh(db_bom)
    return db_bom


@app.put("/api/bom/{bom_id}", response_model=BOMItemResponse)
def update_bom_item(bom_id: int, bom_item: BOMItemUpdate, db: Session = Depends(get_db)):
    """Update a BOM item."""
    db_bom = db.query(BOMItem).get(bom_id)
    if not db_bom:
        raise HTTPException(status_code=404, detail="BOM item not found")
    
    update_data = bom_item.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_bom, key, value)
    
    db.commit()
    db.refresh(db_bom)
    return db_bom


@app.delete("/api/bom/{bom_id}")
def delete_bom_item(bom_id: int, db: Session = Depends(get_db)):
    """Delete a BOM item."""
    db_bom = db.query(BOMItem).get(bom_id)
    if not db_bom:
        raise HTTPException(status_code=404, detail="BOM item not found")
    
    db.delete(db_bom)
    db.commit()
    return {"message": "BOM item deleted successfully"}


@app.get("/api/products/{product_id}/bom-tree")
def get_product_bom_tree(product_id: int, db: Session = Depends(get_db)):
    """Get BOM tree for a product."""
    def build_tree(parent_id: int, level: int = 0):
        if level > 5:
            return []
        
        items = db.query(BOMItem).filter(BOMItem.parent_product_id == parent_id).all()
        result = []
        
        for item in items:
            child = db.query(Product).get(item.child_product_id)
            result.append({
                "id": item.id,
                "product_id": item.child_product_id,
                "code": child.code if child else "Unknown",
                "name": child.name if child else "Unknown",
                "quantity": item.quantity,
                "level": level,
                "children": build_tree(item.child_product_id, level + 1)
            })
        
        return result
    
    return build_tree(product_id)


# ==================== Warehouses ====================

@app.get("/api/warehouses", response_model=List[WarehouseResponse])
def list_warehouses(db: Session = Depends(get_db)):
    """List all warehouses."""
    return db.query(Warehouse).all()


@app.get("/api/warehouses/{warehouse_id}", response_model=WarehouseResponse)
def get_warehouse(warehouse_id: int, db: Session = Depends(get_db)):
    """Get a specific warehouse."""
    warehouse = db.query(Warehouse).get(warehouse_id)
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return warehouse


@app.post("/api/warehouses", response_model=WarehouseResponse)
def create_warehouse(warehouse: WarehouseCreate, db: Session = Depends(get_db)):
    """Create a new warehouse."""
    existing = db.query(Warehouse).filter(Warehouse.code == warehouse.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Warehouse code already exists")
    
    # If this is the default warehouse, unset other defaults
    if warehouse.is_default:
        db.query(Warehouse).update({Warehouse.is_default: False})
    
    db_warehouse = Warehouse(**warehouse.model_dump())
    db.add(db_warehouse)
    db.commit()
    db.refresh(db_warehouse)
    return db_warehouse


@app.put("/api/warehouses/{warehouse_id}", response_model=WarehouseResponse)
def update_warehouse(warehouse_id: int, warehouse: WarehouseUpdate, db: Session = Depends(get_db)):
    """Update a warehouse."""
    db_warehouse = db.query(Warehouse).get(warehouse_id)
    if not db_warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    
    update_data = warehouse.model_dump(exclude_unset=True)
    
    if update_data.get("is_default"):
        db.query(Warehouse).filter(Warehouse.id != warehouse_id).update({Warehouse.is_default: False})
    
    for key, value in update_data.items():
        setattr(db_warehouse, key, value)
    
    db.commit()
    db.refresh(db_warehouse)
    return db_warehouse


# ==================== Inventory ====================

@app.get("/api/inventory", response_model=List[InventoryResponse])
def list_inventory(
    product_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
    low_stock_only: bool = False,
    db: Session = Depends(get_db)
):
    """List inventory records."""
    query = db.query(Inventory).join(Product).join(Warehouse)
    
    if product_id:
        query = query.filter(Inventory.product_id == product_id)
    if warehouse_id:
        query = query.filter(Inventory.warehouse_id == warehouse_id)
    
    inventory = query.all()
    
    if low_stock_only:
        inventory = [
            inv for inv in inventory
            if (inv.quantity - inv.reserved_quantity) < inv.product.min_stock_level
        ]
    
    return inventory


@app.get("/api/inventory/{inventory_id}", response_model=InventoryResponse)
def get_inventory(inventory_id: int, db: Session = Depends(get_db)):
    """Get a specific inventory record."""
    inventory = db.query(Inventory).get(inventory_id)
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")
    return inventory


@app.post("/api/inventory", response_model=InventoryResponse)
def create_or_update_inventory(inventory: InventoryCreate, db: Session = Depends(get_db)):
    """Create or update inventory record."""
    existing = db.query(Inventory).filter(
        Inventory.product_id == inventory.product_id,
        Inventory.warehouse_id == inventory.warehouse_id
    ).first()
    
    if existing:
        # Update existing
        for key, value in inventory.model_dump().items():
            if key not in ["product_id", "warehouse_id"]:
                setattr(existing, key, value)
        db.commit()
        db.refresh(existing)
        return existing
    
    db_inventory = Inventory(**inventory.model_dump())
    db.add(db_inventory)
    db.commit()
    db.refresh(db_inventory)
    return db_inventory


@app.put("/api/inventory/{inventory_id}", response_model=InventoryResponse)
def update_inventory(inventory_id: int, inventory: InventoryUpdate, db: Session = Depends(get_db)):
    """Update inventory."""
    db_inventory = db.query(Inventory).get(inventory_id)
    if not db_inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")
    
    update_data = inventory.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_inventory, key, value)
    
    db.commit()
    db.refresh(db_inventory)
    return db_inventory


# ==================== Inventory Transactions ====================

@app.get("/api/inventory-transactions", response_model=List[InventoryTransactionResponse])
def list_transactions(
    inventory_id: Optional[int] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List inventory transactions."""
    query = db.query(InventoryTransaction)
    
    if inventory_id:
        query = query.filter(InventoryTransaction.inventory_id == inventory_id)
    
    return query.order_by(InventoryTransaction.transaction_date.desc()).limit(limit).all()


@app.post("/api/inventory-transactions", response_model=InventoryTransactionResponse)
def create_transaction(transaction: InventoryTransactionCreate, db: Session = Depends(get_db)):
    """Create inventory transaction and update stock."""
    inventory = db.query(Inventory).get(transaction.inventory_id)
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory record not found")
    
    db_transaction = InventoryTransaction(**transaction.model_dump())
    db.add(db_transaction)
    
    # Update inventory quantity based on transaction type
    qty_change = transaction.quantity
    
    if transaction.transaction_type in [InventoryTransactionType.PURCHASE, InventoryTransactionType.PRODUCTION]:
        inventory.quantity += qty_change
    elif transaction.transaction_type in [InventoryTransactionType.SALE, InventoryTransactionType.ADJUSTMENT]:
        inventory.quantity -= abs(qty_change)
    else:
        # TRANSFER - no net change
        pass
    
    db.commit()
    db.refresh(db_transaction)
    return db_transaction


# ==================== Demand ====================

@app.get("/api/demands", response_model=List[DemandResponse])
def list_demands(
    product_id: Optional[int] = None,
    is_fulfilled: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """List demand records."""
    query = db.query(Demand).join(Product)
    
    if product_id:
        query = query.filter(Demand.product_id == product_id)
    if is_fulfilled is not None:
        query = query.filter(Demand.is_fulfilled == is_fulfilled)
    
    return query.order_by(Demand.due_date).all()


@app.get("/api/demands/{demand_id}", response_model=DemandResponse)
def get_demand(demand_id: int, db: Session = Depends(get_db)):
    """Get a specific demand record."""
    demand = db.query(Demand).get(demand_id)
    if not demand:
        raise HTTPException(status_code=404, detail="Demand not found")
    return demand


@app.post("/api/demands", response_model=DemandResponse)
def create_demand(demand: DemandCreate, db: Session = Depends(get_db)):
    """Create a new demand record."""
    product = db.query(Product).get(demand.product_id)
    if not product:
        raise HTTPException(status_code=400, detail="Product not found")
    
    db_demand = Demand(**demand.model_dump())
    db.add(db_demand)
    db.commit()
    db.refresh(db_demand)
    return db_demand


@app.put("/api/demands/{demand_id}", response_model=DemandResponse)
def update_demand(demand_id: int, demand: DemandUpdate, db: Session = Depends(get_db)):
    """Update a demand record."""
    db_demand = db.query(Demand).get(demand_id)
    if not db_demand:
        raise HTTPException(status_code=404, detail="Demand not found")
    
    update_data = demand.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_demand, key, value)
    
    db.commit()
    db.refresh(db_demand)
    return db_demand


@app.delete("/api/demands/{demand_id}")
def delete_demand(demand_id: int, db: Session = Depends(get_db)):
    """Delete a demand record."""
    db_demand = db.query(Demand).get(demand_id)
    if not db_demand:
        raise HTTPException(status_code=404, detail="Demand not found")
    
    db.delete(db_demand)
    db.commit()
    return {"message": "Demand deleted successfully"}


# ==================== Planned Orders ====================

@app.get("/api/planned-orders", response_model=List[PlannedOrderResponse])
def list_planned_orders(
    product_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """List planned orders."""
    query = db.query(PlannedOrder).join(Product)
    
    if product_id:
        query = query.filter(PlannedOrder.product_id == product_id)
    if status:
        query = query.filter(PlannedOrder.status == status)
    if start_date:
        query = query.filter(PlannedOrder.start_date >= start_date)
    if end_date:
        query = query.filter(PlannedOrder.end_date <= end_date)
    
    return query.order_by(PlannedOrder.start_date).all()


@app.get("/api/planned-orders/{order_id}", response_model=PlannedOrderResponse)
def get_planned_order(order_id: int, db: Session = Depends(get_db)):
    """Get a specific planned order."""
    order = db.query(PlannedOrder).get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Planned order not found")
    return order


@app.put("/api/planned-orders/{order_id}", response_model=PlannedOrderResponse)
def update_planned_order(order_id: int, order: PlannedOrderUpdate, db: Session = Depends(get_db)):
    """Update a planned order."""
    db_order = db.query(PlannedOrder).get(order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="Planned order not found")
    
    update_data = order.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_order, key, value)
    
    db.commit()
    db.refresh(db_order)
    return db_order


# ==================== MRP Calculation ====================

@app.post("/api/mrp/run", response_model=MRPResult)
def run_mrp(params: MRPParameters, db: Session = Depends(get_db)):
    """Run MRP calculation."""
    engine = MRPEngine(db)
    return engine.run_mrp(params)


@app.get("/api/mrp/results")
def get_mrp_results(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Get MRP results (planned orders from latest run)."""
    query = db.query(PlannedOrder).join(Product)
    
    if start_date:
        query = query.filter(PlannedOrder.start_date >= start_date)
    if end_date:
        query = query.filter(PlannedOrder.end_date <= end_date)
    
    orders = query.order_by(PlannedOrder.start_date).all()
    
    # Group by product
    by_product = {}
    for order in orders:
        if order.product_id not in by_product:
            by_product[order.product_id] = {
                "product_id": order.product_id,
                "product_code": order.product.code,
                "product_name": order.product.name,
                "unit": order.product.unit,
                "orders": []
            }
        by_product[order.product_id]["orders"].append({
            "id": order.id,
            "order_type": order.order_type,
            "quantity": order.quantity,
            "start_date": order.start_date.isoformat(),
            "end_date": order.end_date.isoformat(),
            "status": order.status,
            "action_message": order.action_message
        })
    
    return {
        "orders": list(by_product.values()),
        "total_orders": len(orders)
    }


# ==================== Reports ====================

@app.get("/api/reports/inventory-status")
def inventory_status_report(db: Session = Depends(get_db)):
    """Generate inventory status report."""
    inventory = db.query(Inventory).join(Product).join(Warehouse).filter(
        Product.is_active == True
    ).all()
    
    report = []
    for inv in inventory:
        available = inv.quantity - inv.reserved_quantity
        status = "OK"
        if available < 0:
            status = "NEGATIVE"
        elif available < inv.product.safety_stock:
            status = "BELOW SAFETY"
        elif available < inv.product.min_stock_level:
            status = "LOW STOCK"
        
        report.append({
            "product_code": inv.product.code,
            "product_name": inv.product.name,
            "warehouse": inv.warehouse.name,
            "on_hand": inv.quantity,
            "reserved": inv.reserved_quantity,
            "available": available,
            "min_level": inv.product.min_stock_level,
            "safety_stock": inv.product.safety_stock,
            "status": status,
            "value": round(available * inv.product.unit_cost, 2)
        })
    
    return report


@app.get("/api/reports/mrp-coverage")
def mrp_coverage_report(
    start_date: date = None,
    end_date: date = None,
    db: Session = Depends(get_db)
):
    """Generate MRP coverage report."""
    if not start_date:
        start_date = date.today()
    if not end_date:
        end_date = start_date + timedelta(days=30)
    
    # Get demands
    demands = db.query(Demand).filter(
        Demand.due_date >= start_date,
        Demand.due_date <= end_date
    ).all()
    
    # Get planned orders
    orders = db.query(PlannedOrder).filter(
        PlannedOrder.start_date >= start_date,
        PlannedOrder.start_date <= end_date
    ).all()
    
    # Group by product
    coverage = {}
    
    for demand in demands:
        pid = demand.product_id
        if pid not in coverage:
            coverage[pid] = {
                "product_id": pid,
                "product_code": demand.product.code,
                "product_name": demand.product.name,
                "total_demand": 0,
                "planned_orders": []
            }
        coverage[pid]["total_demand"] += demand.quantity
    
    for order in orders:
        pid = order.product_id
        if pid in coverage:
            coverage[pid]["planned_orders"].append({
                "quantity": order.quantity,
                "date": order.start_date.isoformat()
            })
    
    # Calculate coverage percentage
    result = []
    for pid, data in coverage.items():
        total_planned = sum(o["quantity"] for o in data["planned_orders"])
        coverage_pct = (total_planned / data["total_demand"] * 100) if data["total_demand"] > 0 else 100
        
        result.append({
            **data,
            "total_planned": total_planned,
            "coverage_percentage": round(coverage_pct, 2),
            "coverage_status": "COVERED" if coverage_pct >= 100 else "PARTIAL"
        })
    
    return result


# ==================== Frontend ====================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the frontend application."""
    with open("index.html", "r") as f:
        return f.read()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

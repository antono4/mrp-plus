"""Script to populate MRP++ database with sample data."""

from database import SessionLocal, init_db
from models import Product, Warehouse, Inventory, BOMItem, Demand, ProductType, LotSizingMethod
from datetime import date, timedelta

def create_sample_data():
    init_db()
    db = SessionLocal()
    
    try:
        # Check if data already exists
        existing = db.query(Product).first()
        if existing:
            print("Sample data already exists!")
            return
        
        # Create Warehouses
        warehouses = [
            Warehouse(code="WH-01", name="Main Warehouse", location="Building A", is_default=True),
            Warehouse(code="WH-02", name="Secondary Warehouse", location="Building B", is_default=False),
        ]
        db.add_all(warehouses)
        db.commit()
        print("Warehouses created")
        
        # Create Products
        products = [
            # Raw Materials
            Product(code="RM-001", name="Steel Sheet 2mm", product_type=ProductType.RAW_MATERIAL, 
                   unit="KG", unit_cost=2.50, min_stock_level=500, safety_stock=100, lead_time_days=3),
            Product(code="RM-002", name="Aluminum Rod 10mm", product_type=ProductType.RAW_MATERIAL,
                   unit="KG", unit_cost=4.00, min_stock_level=300, safety_stock=50, lead_time_days=5),
            Product(code="RM-003", name="Plastic Pellets", product_type=ProductType.RAW_MATERIAL,
                   unit="KG", unit_cost=1.50, min_stock_level=200, safety_stock=30, lead_time_days=2),
            Product(code="RM-004", name="Copper Wire", product_type=ProductType.RAW_MATERIAL,
                   unit="M", unit_cost=0.80, min_stock_level=1000, safety_stock=200, lead_time_days=4),
            
            # Components
            Product(code="CP-001", name="Bearing Assembly", product_type=ProductType.COMPONENT,
                   unit="PCS", unit_cost=5.00, min_stock_level=100, safety_stock=20, lead_time_days=2,
                   lot_sizing_method=LotSizingMethod.EOQ),
            Product(code="CP-002", name="Motor Unit", product_type=ProductType.COMPONENT,
                   unit="PCS", unit_cost=25.00, min_stock_level=50, safety_stock=10, lead_time_days=5,
                   lot_sizing_method=LotSizingMethod.FOQ, fixed_order_qty=50),
            Product(code="CP-003", name="Control Board", product_type=ProductType.COMPONENT,
                   unit="PCS", unit_cost=15.00, min_stock_level=75, safety_stock=15, lead_time_days=3),
            
            # Finished Goods
            Product(code="FG-001", name="Standard Motor 1HP", product_type=ProductType.FINISHED_GOOD,
                   unit="PCS", unit_cost=75.00, min_stock_level=25, safety_stock=5, lead_time_days=7,
                   lot_sizing_method=LotSizingMethod.LFL),
            Product(code="FG-002", name="Premium Motor 2HP", product_type=ProductType.FINISHED_GOOD,
                   unit="PCS", unit_cost=120.00, min_stock_level=15, safety_stock=3, lead_time_days=10,
                   lot_sizing_method=LotSizingMethod.POQ),
            Product(code="FG-003", name="Industrial Pump", product_type=ProductType.FINISHED_GOOD,
                   unit="PCS", unit_cost=150.00, min_stock_level=10, safety_stock=2, lead_time_days=14),
        ]
        db.add_all(products)
        db.commit()
        print("Products created")
        
        # Create Inventory records
        inventory_records = [
            Inventory(product_id=1, warehouse_id=1, quantity=600, reorder_point=100),
            Inventory(product_id=2, warehouse_id=1, quantity=350, reorder_point=50),
            Inventory(product_id=3, warehouse_id=1, quantity=180, reorder_point=30),
            Inventory(product_id=4, warehouse_id=1, quantity=1200, reorder_point=200),
            Inventory(product_id=5, warehouse_id=1, quantity=90, reorder_point=20),
            Inventory(product_id=6, warehouse_id=1, quantity=60, reorder_point=10),
            Inventory(product_id=7, warehouse_id=1, quantity=80, reorder_point=15),
            Inventory(product_id=8, warehouse_id=1, quantity=30, reorder_point=5),
            Inventory(product_id=9, warehouse_id=1, quantity=18, reorder_point=3),
            Inventory(product_id=10, warehouse_id=1, quantity=12, reorder_point=2),
        ]
        db.add_all(inventory_records)
        db.commit()
        print("Inventory records created")
        
        # Create BOM Items
        bom_items = [
            # Standard Motor 1HP - 3 levels
            BOMItem(parent_product_id=8, child_product_id=5, quantity=4),  # 4 bearings
            BOMItem(parent_product_id=8, child_product_id=6, quantity=1),   # 1 motor unit
            BOMItem(parent_product_id=8, child_product_id=7, quantity=1),    # 1 control board
            
            # Control Board components
            BOMItem(parent_product_id=7, child_product_id=1, quantity=0.5),  # 0.5 kg steel
            BOMItem(parent_product_id=7, child_product_id=4, quantity=2),  # 2m copper wire
            
            # Premium Motor 2HP
            BOMItem(parent_product_id=9, child_product_id=5, quantity=6),  # 6 bearings
            BOMItem(parent_product_id=9, child_product_id=6, quantity=2),  # 2 motor units
            BOMItem(parent_product_id=9, child_product_id=7, quantity=2),  # 2 control boards
            
            # Industrial Pump
            BOMItem(parent_product_id=10, child_product_id=6, quantity=1),
            BOMItem(parent_product_id=10, child_product_id=3, quantity=2),  # 2kg plastic
            BOMItem(parent_product_id=10, child_product_id=2, quantity=1),  # 1kg aluminum
        ]
        db.add_all(bom_items)
        db.commit()
        print("BOM items created")
        
        # Create Demand (sales orders)
        today = date.today()
        demands = [
            Demand(product_id=8, demand_type="sales_order", reference_number="SO-2024-001",
                   quantity=15, due_date=today + timedelta(days=7), priority=1),
            Demand(product_id=8, demand_type="sales_order", reference_number="SO-2024-002",
                   quantity=10, due_date=today + timedelta(days=14), priority=2),
            Demand(product_id=9, demand_type="sales_order", reference_number="SO-2024-003",
                   quantity=8, due_date=today + timedelta(days=10), priority=1),
            Demand(product_id=10, demand_type="forecast", reference_number="FC-2024-Q1",
                   quantity=20, due_date=today + timedelta(days=21), priority=3),
            Demand(product_id=10, demand_type="sales_order", reference_number="SO-2024-004",
                   quantity=5, due_date=today + timedelta(days=14), priority=1),
        ]
        db.add_all(demands)
        db.commit()
        print("Demands created")
        
        print("\n✅ Sample data created successfully!")
        print(f"   - {len(warehouses)} Warehouses")
        print(f"   - {len(products)} Products")
        print(f"   - {len(inventory_records)} Inventory Records")
        print(f"   - {len(bom_items)} BOM Items")
        print(f"   - {len(demands)} Demand Records")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_sample_data()

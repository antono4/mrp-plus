"""Database models for MRP++ application."""

from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, Enum, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()


class ProductType(enum.Enum):
    RAW_MATERIAL = "raw_material"
    COMPONENT = "component"
    FINISHED_GOOD = "finished_good"


class InventoryTransactionType(enum.Enum):
    PURCHASE = "purchase"
    PRODUCTION = "production"
    SALE = "sale"
    ADJUSTMENT = "adjustment"
    TRANSFER = "transfer"


class LotSizingMethod(enum.Enum):
    LFL = "lfl"  # Lot for Lot
    FOQ = "foq"  # Fixed Order Quantity
    EOQ = "eoq"  # Economic Order Quantity
    POQ = "poq"  # Period Order Quantity


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    product_type = Column(Enum(ProductType), nullable=False)
    unit = Column(String(20), default="PCS")
    category = Column(String(100), nullable=True)
    unit_cost = Column(Float, default=0.0)
    min_stock_level = Column(Float, default=0.0)
    safety_stock = Column(Float, default=0.0)
    lead_time_days = Column(Integer, default=1)
    lot_sizing_method = Column(Enum(LotSizingMethod), default=LotSizingMethod.LFL)
    fixed_order_qty = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    bom_items_as_parent = relationship("BOMItem", foreign_keys="BOMItem.parent_product_id", back_populates="parent_product")
    bom_items_as_child = relationship("BOMItem", foreign_keys="BOMItem.child_product_id", back_populates="child_product")
    inventory_records = relationship("Inventory", back_populates="product")
    demand_records = relationship("Demand", back_populates="product")


class BOMItem(Base):
    __tablename__ = "bom_items"

    id = Column(Integer, primary_key=True, index=True)
    parent_product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    child_product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    is_optional = Column(Boolean, default=False)
    scrap_percentage = Column(Float, default=0.0)
    effective_from = Column(Date, nullable=True)
    effective_to = Column(Date, nullable=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    parent_product = relationship("Product", foreign_keys=[parent_product_id], back_populates="bom_items_as_parent")
    child_product = relationship("Product", foreign_keys=[child_product_id], back_populates="bom_items_as_child")


class Warehouse(Base):
    __tablename__ = "warehouses"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    location = Column(String(200), nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    inventory_records = relationship("Inventory", back_populates="warehouse")


class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    quantity = Column(Float, default=0.0)
    reserved_quantity = Column(Float, default=0.0)
    reorder_point = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    product = relationship("Product", back_populates="inventory_records")
    warehouse = relationship("Warehouse", back_populates="inventory_records")
    transactions = relationship("InventoryTransaction", back_populates="inventory")


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id = Column(Integer, primary_key=True, index=True)
    inventory_id = Column(Integer, ForeignKey("inventory.id"), nullable=False)
    transaction_type = Column(Enum(InventoryTransactionType), nullable=False)
    quantity = Column(Float, nullable=False)
    reference_number = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    transaction_date = Column(DateTime, default=datetime.utcnow)

    # Relationships
    inventory = relationship("Inventory", back_populates="transactions")


class Demand(Base):
    __tablename__ = "demands"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    demand_type = Column(String(50), nullable=False)  # 'sales_order', 'forecast'
    reference_number = Column(String(100), nullable=True)
    quantity = Column(Float, nullable=False)
    priority = Column(Integer, default=1)  # 1 = highest
    due_date = Column(Date, nullable=False)
    is_fulfilled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    product = relationship("Product", back_populates="demand_records")


class PlannedOrder(Base):
    __tablename__ = "planned_orders"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    order_type = Column(String(50), nullable=False)  # 'purchase', 'production'
    quantity = Column(Float, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(String(50), default="proposed")  # 'proposed', 'released', 'completed', 'cancelled'
    priority = Column(Integer, default=1)
    notes = Column(Text, nullable=True)
    action_message = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    product = relationship("Product")


class MRPRun(Base):
    __tablename__ = "mrp_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_date = Column(DateTime, default=datetime.utcnow)
    planning_horizon_start = Column(Date, nullable=False)
    planning_horizon_end = Column(Date, nullable=False)
    status = Column(String(50), default="completed")
    notes = Column(Text, nullable=True)

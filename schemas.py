"""Pydantic schemas for MRP++ API."""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from enum import Enum


class ProductType(str, Enum):
    RAW_MATERIAL = "raw_material"
    COMPONENT = "component"
    FINISHED_GOOD = "finished_good"


class LotSizingMethod(str, Enum):
    LFL = "lfl"
    FOQ = "foq"
    EOQ = "eoq"
    POQ = "poq"


class InventoryTransactionType(str, Enum):
    PURCHASE = "purchase"
    PRODUCTION = "production"
    SALE = "sale"
    ADJUSTMENT = "adjustment"
    TRANSFER = "transfer"


# Product Schemas
class ProductBase(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    product_type: ProductType
    unit: str = "PCS"
    category: Optional[str] = None
    unit_cost: float = 0.0
    min_stock_level: float = 0.0
    safety_stock: float = 0.0
    lead_time_days: int = 1
    lot_sizing_method: LotSizingMethod = LotSizingMethod.LFL
    fixed_order_qty: float = 0.0


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    product_type: Optional[ProductType] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    unit_cost: Optional[float] = None
    min_stock_level: Optional[float] = None
    safety_stock: Optional[float] = None
    lead_time_days: Optional[int] = None
    lot_sizing_method: Optional[LotSizingMethod] = None
    fixed_order_qty: Optional[float] = None
    is_active: Optional[bool] = None


class ProductResponse(ProductBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# BOM Schemas
class BOMItemBase(BaseModel):
    parent_product_id: int
    child_product_id: int
    quantity: float
    is_optional: bool = False
    scrap_percentage: float = 0.0
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None


class BOMItemCreate(BOMItemBase):
    pass


class BOMItemUpdate(BaseModel):
    quantity: Optional[float] = None
    is_optional: Optional[bool] = None
    scrap_percentage: Optional[float] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None


class BOMItemResponse(BOMItemBase):
    id: int
    version: int
    created_at: datetime
    parent_product: Optional[ProductResponse] = None
    child_product: Optional[ProductResponse] = None

    class Config:
        from_attributes = True


class BOMWithChildren(BOMItemResponse):
    children: List["BOMWithChildren"] = []


# Warehouse Schemas
class WarehouseBase(BaseModel):
    code: str
    name: str
    location: Optional[str] = None
    is_default: bool = False


class WarehouseCreate(WarehouseBase):
    pass


class WarehouseUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    is_default: Optional[bool] = None


class WarehouseResponse(WarehouseBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Inventory Schemas
class InventoryBase(BaseModel):
    product_id: int
    warehouse_id: int
    quantity: float = 0.0
    reserved_quantity: float = 0.0
    reorder_point: float = 0.0


class InventoryCreate(InventoryBase):
    pass


class InventoryUpdate(BaseModel):
    quantity: Optional[float] = None
    reserved_quantity: Optional[float] = None
    reorder_point: Optional[float] = None


class InventoryResponse(InventoryBase):
    id: int
    updated_at: datetime
    product: Optional[ProductResponse] = None
    warehouse: Optional[WarehouseResponse] = None

    class Config:
        from_attributes = True


# Inventory Transaction Schemas
class InventoryTransactionBase(BaseModel):
    inventory_id: int
    transaction_type: InventoryTransactionType
    quantity: float
    reference_number: Optional[str] = None
    notes: Optional[str] = None


class InventoryTransactionCreate(InventoryTransactionBase):
    pass


class InventoryTransactionResponse(InventoryTransactionBase):
    id: int
    transaction_date: datetime

    class Config:
        from_attributes = True


# Demand Schemas
class DemandBase(BaseModel):
    product_id: int
    demand_type: str
    reference_number: Optional[str] = None
    quantity: float
    priority: int = 1
    due_date: date


class DemandCreate(DemandBase):
    pass


class DemandUpdate(BaseModel):
    quantity: Optional[float] = None
    priority: Optional[int] = None
    due_date: Optional[date] = None
    is_fulfilled: Optional[bool] = None


class DemandResponse(DemandBase):
    id: int
    is_fulfilled: bool
    created_at: datetime
    product: Optional[ProductResponse] = None

    class Config:
        from_attributes = True


# Planned Order Schemas
class PlannedOrderBase(BaseModel):
    product_id: int
    order_type: str
    quantity: float
    start_date: date
    end_date: date
    status: str = "proposed"
    priority: int = 1
    notes: Optional[str] = None


class PlannedOrderCreate(PlannedOrderBase):
    pass


class PlannedOrderUpdate(BaseModel):
    quantity: Optional[float] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    notes: Optional[str] = None


class PlannedOrderResponse(PlannedOrderBase):
    id: int
    action_message: Optional[str] = None
    created_at: datetime
    product: Optional[ProductResponse] = None

    class Config:
        from_attributes = True


# MRP Calculation Schemas
class MRPParameters(BaseModel):
    planning_horizon_start: date
    planning_horizon_end: date
    use_safety_stock: bool = True
    use_min_stock_level: bool = True


class MRPRequirement(BaseModel):
    product_id: int
    product_code: str
    product_name: str
    period: str
    gross_requirement: float
    scheduled_receipts: float
    projected_on_hand: float
    net_requirement: float
    planned_order_quantity: float
    planned_order_date: Optional[date] = None
    action_message: Optional[str] = None


class MRPResult(BaseModel):
    run_id: int
    run_date: datetime
    planning_horizon_start: date
    planning_horizon_end: date
    requirements: List[MRPRequirement]
    summary: dict


# Dashboard Schemas
class DashboardSummary(BaseModel):
    total_products: int
    total_demands: int
    pending_orders: int
    low_stock_items: int
    inventory_value: float


class StockAlert(BaseModel):
    product_id: int
    product_code: str
    product_name: str
    current_stock: float
    min_stock_level: float
    warehouse_name: str


# Update forward references
BOMWithChildren.model_rebuild()

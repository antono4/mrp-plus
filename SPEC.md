# MRP++ Application Specification

## 1. Project Overview

**Project Name**: MRP++ (Material Requirements Planning Plus)

**Core Functionality**: A comprehensive Material Requirements Planning system that helps manufacturing companies manage inventory, calculate material needs based on production schedules, and optimize procurement with intelligent lead time and lot sizing calculations.

**Target Users**: Manufacturing planners, production managers, procurement teams, and inventory managers.

## 2. UI/UX Specification

### Layout Structure

**Main Navigation**
- Sidebar navigation (240px width) with collapsible menu
- Top header bar with search, notifications, and user profile
- Main content area with responsive grid layout

**Page Sections**
- Dashboard: Overview cards, charts, and alerts
- Products: Product master data management
- Bill of Materials: Multi-level BOM management
- Inventory: Current stock levels and movements
- Demand: Sales orders and forecasts
- MRP Results: Calculated requirements and recommendations
- Reports: Analytics and export functionality

### Visual Design

**Color Palette**
- Primary: `#1E3A5F` (Deep Navy Blue)
- Secondary: `#2E7D32` (Forest Green)
- Accent: `#FF6B35` (Vibrant Orange)
- Background: `#F5F7FA` (Light Gray)
- Card Background: `#FFFFFF`
- Text Primary: `#1A1A2E`
- Text Secondary: `#6B7280`
- Success: `#10B981`
- Warning: `#F59E0B`
- Danger: `#EF4444`
- Border: `#E5E7EB`

**Typography**
- Headings: 'Inter', sans-serif
  - H1: 28px, weight 700
  - H2: 22px, weight 600
  - H3: 18px, weight 600
- Body: 'Inter', sans-serif, 14px, weight 400
- Labels: 12px, weight 500, uppercase

**Spacing System**
- Base unit: 4px
- Margins: 16px, 24px, 32px
- Padding: 8px, 12px, 16px, 24px
- Card border-radius: 12px
- Button border-radius: 8px

**Visual Effects**
- Card shadows: `0 1px 3px rgba(0,0,0,0.1), 0 1px 2px rgba(0,0,0,0.06)`
- Hover shadows: `0 4px 6px rgba(0,0,0,0.1)`
- Transitions: 200ms ease-in-out

### Components

**Navigation Sidebar**
- Logo at top
- Menu items with icons
- Active state: Background `#E8F4FD`, left border 3px accent color
- Hover state: Background `#F0F4F8`

**Cards**
- White background, rounded corners
- Header with title and action buttons
- Hover: Slight elevation increase

**Data Tables**
- Striped rows (alternating `#F9FAFB`)
- Sortable columns with indicators
- Row hover: Background `#F3F4F6`
- Pagination at bottom

**Buttons**
- Primary: Background `#1E3A5F`, white text
- Secondary: Border `#1E3A5F`, navy text
- Danger: Background `#EF4444`
- Disabled: Opacity 0.5, cursor not-allowed

**Forms**
- Input fields: Border `#D1D5DB`, focus border `#1E3A5F`
- Labels: Above input, 12px uppercase
- Error messages: Red text below input

**Charts**
- Line charts for trends
- Bar charts for comparisons
- Pie charts for distributions
- Color scheme matching palette

## 3. Functionality Specification

### Core Features

**1. Product Management**
- Create, read, update, delete products
- Product attributes: code, name, description, unit, category
- Product types: Raw Material, Component, Finished Good
- Default supplier assignment
- Minimum stock level setting

**2. Bill of Materials (BOM)**
- Multi-level BOM structure (up to 5 levels)
- Parent-child relationships with quantities
- BOM versioning with effective dates
- Copy and clone BOM functionality
- BOM validation (circular reference check)

**3. Inventory Management**
- Current stock tracking per warehouse
- Stock movements (IN/OUT)
- Batch and lot tracking
- Inventory valuation (FIFO, Average)
- Low stock alerts
- Reorder point configuration

**4. Demand Management**
- Sales order entry
- Forecast entry (monthly/weekly)
- Demand aggregation by period
- Priority assignment
- Demand vs. supply visibility

**5. MRP Calculation Engine**
- Net requirements calculation
- Gross requirements from independent demand
- Scheduled receipts inclusion
- Lead time consideration
- Safety stock levels
- Lot sizing methods: LFL, FOQ, EOQ, Period Order Quantity

**6. MRP Results & Recommendations**
- Planned order proposals
- Order timing recommendations
- Purchase requisition generation
- Work order suggestions
- Action messages (order, reschedule, cancel)

**7. Reporting & Analytics**
- Inventory status dashboard
- MRP coverage report
- Stock trends analysis
- Order fulfillment metrics
- Export to CSV/PDF

### User Interactions and Flows

**MRP Calculation Flow**
1. User selects planning horizon (weeks/months)
2. System aggregates demand for period
3. BOM explosion calculates gross requirements
4. Net requirements = Gross - Available - Scheduled
5. Apply lot sizing rules
6. Generate planned orders considering lead times
7. Display results with action recommendations

**Data Handling**
- All data stored in SQLite database
- Automatic data validation
- Audit trail for changes
- Session-based user preferences

### Edge Cases
- Circular BOM references → Show validation error
- Negative inventory → Warning indicator
- Insufficient stock → Highlight shortage
- No BOM for product → Skip explosion
- Lead time = 0 → Immediate requirement

## 4. Technical Stack

**Backend**: Python FastAPI
**Database**: SQLite with SQLAlchemy ORM
**Frontend**: HTML5, CSS3, Vanilla JavaScript
**Charts**: Chart.js
**Icons**: Lucide Icons (CDN)

## 5. Acceptance Criteria

### Visual Checkpoints
- [ ] Sidebar navigation renders correctly with all menu items
- [ ] Dashboard displays summary cards with charts
- [ ] Forms validate input and show appropriate error messages
- [ ] Tables support sorting and pagination
- [ ] Charts render with correct color scheme

### Functional Checkpoints
- [ ] Products can be CRUD operated
- [ ] BOM supports multi-level structure
- [ ] MRP calculation produces correct net requirements
- [ ] Low stock alerts trigger appropriately
- [ ] Reports generate accurate data
- [ ] All navigation links work correctly

### Data Integrity
- [ ] BOM circular reference detection works
- [ ] Stock calculations are accurate
- [ ] MRP results match manual calculations

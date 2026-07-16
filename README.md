# MRP++ | Material Requirements Planning Plus

<div align="center">

![MRP++ Logo](https://img.shields.io/badge/MRP++-Material%20Requirements%20Planning-1E3A5F?style=for-the-badge&logo=python&logoColor=white)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg?style=flat&logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-00a89d?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=flat)](LICENSE)

**Advanced Manufacturing Planning System** - Sistem perencanaan kebutuhan material untuk industri manufaktur.

[Features](#fitur) • [Installation](#instalasi) • [Usage](#penggunaan) • [API](#api) • [Contributing](#contributing)

</div>

---

## ✨ Fitur

### 📦 Product Management
- CRUD produk dengan 3 tipe: Raw Material, Component, Finished Good
- Konfigurasi lot sizing (LFL, FOQ, EOQ, POQ)
- Lead time, safety stock, minimum stock level

### 📋 Bill of Materials (BOM)
- Struktur multi-level BOM (up to 5 level)
- BOM explosion untuk MRP calculation
- Deteksi circular reference

### 📊 Inventory Management
- Stock tracking per warehouse
- Inventory transactions (purchase, production, sale)
- Low stock alerts

### 📈 Demand Management
- Sales orders & forecasts
- Priority-based planning
- Due date tracking

### 🧮 MRP Calculation Engine
- Net requirements calculation
- BOM explosion (multi-level)
- Multiple lot sizing methods:
  - **LFL** (Lot for Lot)
  - **FOQ** (Fixed Order Quantity)
  - **EOQ** (Economic Order Quantity)
  - **POQ** (Period Order Quantity)
- Planned order generation

### 📉 Reports & Analytics
- Dashboard dengan statistik real-time
- Inventory status report
- MRP coverage report
- Charts dan visualisasi

---

## 🚀 Instalasi

### Prerequisites
- Python 3.11+
- pip

### Steps

```bash
# Clone repository
git clone https://github.com/antono4/mrp-plus.git
cd mrp-plus

# Install dependencies
pip install -r requirements.txt

# (Optional) Populate sample data
python sample_data.py

# Run application
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Docker (Optional)

```bash
# Build image
docker build -t mrp-plus .

# Run container
docker run -p 8000:8000 mrp-plus
```

---

## 🖥️ Penggunaan

### Access Points

| Service | URL |
|---------|-----|
| **Frontend** | http://localhost:8000/ |
| **API Docs** | http://localhost:8000/docs |
| **ReDoc** | http://localhost:8000/redoc |

### Default Sample Data

Setelah menjalankan `python sample_data.py`, Anda akan memiliki:

| Type | Count |
|------|-------|
| Warehouses | 2 |
| Products | 10 |
| Inventory Records | 10 |
| BOM Items | 11 |
| Demands | 5 |

### Product Structure

```
Finished Goods (FG)
├── FG-001: Standard Motor 1HP
├── FG-002: Premium Motor 2HP
└── FG-003: Industrial Pump
    │
    └── Components (CP)
        ├── CP-001: Bearing Assembly
        ├── CP-002: Motor Unit
        └── CP-003: Control Board
            │
            └── Raw Materials (RM)
                ├── RM-001: Steel Sheet 2mm
                ├── RM-002: Aluminum Rod 10mm
                ├── RM-003: Plastic Pellets
                └── RM-004: Copper Wire
```

---

## 📖 API

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/dashboard` | Dashboard summary |
| GET | `/api/products` | List all products |
| POST | `/api/products` | Create product |
| GET | `/api/bom` | List BOM items |
| POST | `/api/bom` | Create BOM item |
| GET | `/api/inventory` | List inventory |
| POST | `/api/inventory` | Create/update inventory |
| GET | `/api/demands` | List demands |
| POST | `/api/demands` | Create demand |
| POST | `/api/mrp/run` | Run MRP calculation |
| GET | `/api/planned-orders` | List planned orders |
| GET | `/api/reports/inventory-status` | Inventory status report |
| GET | `/api/reports/mrp-coverage` | MRP coverage report |

### Example: Run MRP

```bash
curl -X POST http://localhost:8000/api/mrp/run \
  -H "Content-Type: application/json" \
  -d '{
    "planning_horizon_start": "2024-01-01",
    "planning_horizon_end": "2024-03-31",
    "use_safety_stock": true,
    "use_min_stock_level": true
  }'
```

---

## 🏗️ Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, SQLAlchemy |
| Database | SQLite |
| Frontend | Vanilla JavaScript, HTML5, CSS3 |
| Charts | Chart.js |
| Icons | Lucide Icons |

---

## 📁 Project Structure

```
mrp-plus/
├── main.py           # FastAPI application
├── models.py         # Database models
├── schemas.py        # Pydantic schemas
├── database.py       # Database configuration
├── mrp_engine.py    # MRP calculation logic
├── sample_data.py   # Sample data seeder
├── index.html       # Frontend SPA
├── requirements.txt # Dependencies
├── SPEC.md          # Project specification
└── README.md        # This file
```

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Author

**Antono** - [GitHub](https://github.com/antono4)

---

<div align="center">

⭐ Star this repo if you find it helpful!

</div>

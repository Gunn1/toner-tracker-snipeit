from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from dotenv import load_dotenv
import requests
import os
import snipeit
import json
from typing import List
from fastapi import Depends
import json
CONFIG_FILE = "consumables_mapping.config"
def load_printer_settings(file_path="consumables_mapping.config"):
    with open(file_path, "r") as f:
        config = json.load(f)
    return config.get("PREDEFINED_CONSUMABLES", {})
# Load environment variables
load_dotenv()

SNIPEIT_API_KEY = os.getenv("SNIPEIT_API_KEY")
SNIPEIT_BASE_URL = os.getenv("SNIPEIT_BASE_URL")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./toner.db")

# Set up DB
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Jinja2 Templates
templates = Jinja2Templates(directory="templates")

from pydantic import BaseModel
from typing import Optional
# Define TonerModel FIRST
class TonerModel(Base):
    __tablename__ = "toner_models"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    printer_model = Column(String)
    color = Column(String)
    part_number = Column(String)

    # New relationship to consumables
    consumables = relationship("Consumable", back_populates="toner_model")
class Consumable(Base):
    __tablename__ = "consumables"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    type = Column(String)  # e.g. Toner, Drum, etc.
    part_number = Column(String)
    snipeit_asset_id = Column(String, nullable=True)  # new field for Snipe‑IT asset ID
    toner_model_id = Column(Integer, ForeignKey("toner_models.id"))

    toner_model = relationship("TonerModel", back_populates="consumables")


class ConsumableSchema(BaseModel):
    id: int
    name: str
    type: str
    part_number: str

    model_config = {
        "from_attributes": True
    }

class TonerModelSchema(BaseModel):
    id: int
    name: str
    printer_model: str
    color: Optional[str] = None
    part_number: Optional[str] = None
    consumables: List[ConsumableSchema] = []

    model_config = {
        "from_attributes": True
    }

class PrinterSchema(BaseModel):
    id: int
    asset_tag: str
    name: str
    user: Optional[str]
    location: Optional[str]
    ip_address: Optional[str]
    toner_model: TonerModelSchema

    model_config = {
        "from_attributes": True
    }


class Printer(Base):
    __tablename__ = "printers"
    id = Column(Integer, primary_key=True, index=True)
    asset_tag = Column(String, unique=True, index=True)  # <- NEW UNIQUE FIELD
    name = Column(String, index=True)
    location = Column(String)
    ip_address = Column(String)
    user = Column(String)
    toner_model_id = Column(Integer, ForeignKey("toner_models.id"))

    toner_model = relationship("TonerModel")




# Create tables
Base.metadata.create_all(bind=engine)

# FastAPI app
app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Printers Snipe-IT 
# Get Toner For those printers
# Trying to get supply levels for those printers and there location, status and who uses that printer.
def sync_consumables_with_snipeit(snipeconn: snipeit.SnipeConnect, db: Session):
    consumables = db.query(Consumable).all()
    for consumable in consumables:
        # Use the part number as the search query.
        search_query = consumable.part_number
        response = snipeconn.consumables_search("/consumables", search_query)
        data = json.loads(response)
        print(data)
        rows = data.get("rows", [])
        matched_asset = None
        
        for asset in rows:
            # Get the model info from the asset.
            model_number = asset.get("model_number")
            # Compare the asset's model number with the consumable's part number.
            if model_number == search_query:
                matched_asset = asset
                break
        
        if matched_asset:
            consumable.snipeit_asset_id = matched_asset.get("id")
            print(f"Linked {consumable.name} (Part: {consumable.part_number}) with Snipe‑IT asset ID {consumable.snipeit_asset_id}")
        else:
            print(f"No Snipe‑IT asset found for {consumable.name} with part {consumable.part_number}")
    
    db.commit()


def get_all_printers(snipeconn: snipeit.SnipeConnect):
    all_rows = []
    page = 1

    while True:
        response = snipeconn.asset_search("/hardware", "printers & scanners")
        data = json.loads(response)
        rows = data.get("rows", [])

        if not rows:
            break  # No more results

        all_rows.extend(rows)
        page += 1

    return all_rows
def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(config: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

@app.get("/config", response_class=HTMLResponse)
async def edit_config_page(request: Request):
    config = load_config()
    # Convert config to formatted JSON string
    config_str = json.dumps(config, indent=4)
    return templates.TemplateResponse("edit_config.html", {"request": request, "config": config_str})

@app.post("/config", response_class=HTMLResponse)
async def update_config(request: Request, config_data: str = Form(...)):
    try:
        updated_config = json.loads(config_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid JSON data")
    
    save_config(updated_config)
    message = "Configuration updated successfully."
    # Return the updated JSON string in the form.
    config_str = json.dumps(updated_config, indent=4)
    return templates.TemplateResponse("edit_config.html", {"request": request, "config": config_str, "message": message})

snipeconn = snipeit.SnipeConnect(SNIPEIT_API_KEY,SNIPEIT_BASE_URL)
def sync_printers_from_snipeit(snipeconn: snipeit.SnipeConnect, db: Session):
    # Optional: Predefined consumables by printer model
    PREDEFINED_CONSUMABLES = load_printer_settings()

    for model_name, consumables in PREDEFINED_CONSUMABLES.items():
        toner_model = db.query(TonerModel).filter_by(printer_model=model_name).first()

        if not toner_model:
            toner_model = TonerModel(
                name=model_name,
                printer_model=model_name,
                color=None,
                part_number=None
            )
            db.add(toner_model)
            db.commit()
            db.refresh(toner_model)

        # 🔥 DELETE all existing consumables for this toner model
        db.query(Consumable).filter_by(toner_model_id=toner_model.id).delete()
        db.commit()

        # ✅ RE-ADD all predefined consumables
        for c in consumables:
            db.add(Consumable(
                name=c["name"],
                type=c["type"],
                part_number=c["part_number"],
                toner_model=toner_model
            ))

        db.commit()



    # Fetch printers from Snipe-IT
    response = snipeconn.asset_search("/hardware", 9)  # 9 = your category_id
    data = json.loads(response)
    rows = data.get("rows", [])

    for item in rows:
        name = item.get("name")
        location = (item.get("location") or item.get("rtd_location") or {}).get("name", "")
        ip_address = item.get("custom_fields", {}).get("IP Address", {}).get("value", "")
        model_name = item.get("model", {}).get("name")
        asset_tag = item.get("asset_tag")
        assigned_to = item.get("assigned_to")
        if assigned_to and isinstance(assigned_to, dict) and assigned_to.get("type") == "user":
            user = assigned_to.get("name", "")
        else:
            user = ""


        if not asset_tag or not model_name:
            print(f"Skipping invalid printer (missing asset_tag or model): {item}")
            continue

        print(f"Adding printer: {asset_tag}, model: {model_name}")

        # Get or create toner model
        toner_model = db.query(TonerModel).filter_by(printer_model=model_name).first()
        if not toner_model:
            toner_model = TonerModel(name=model_name, printer_model=model_name)
            db.add(toner_model)
            db.commit()
            db.refresh(toner_model)

        # Get or create printer
        printer = db.query(Printer).filter_by(asset_tag=asset_tag).first()
        if printer:
            printer.name = name
            printer.location = location
            printer.ip_address = ip_address
            printer.user = user
            printer.toner_model_id = toner_model.id
        else:
            printer = Printer(
                asset_tag=asset_tag,
                name=name,
                location=location,
                ip_address=ip_address,
                toner_model_id=toner_model.id
            )
            db.add(printer)

    db.commit()
    print(f"Total printers in session: {db.query(Printer).count()}")

@app.post("/sync-consumables")
def trigger_sync_consumables(db: Session = Depends(get_db)):
    try:
        sync_consumables_with_snipeit(snipeconn, db)
        return {"message": "Consumables synced with Snipe‑IT successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sync-printers")
def trigger_sync(db: Session = Depends(get_db)):
    try:
        sync_printers_from_snipeit(snipeconn, db)
        return {"message": "Printers synced successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/printers", response_model=List[PrinterSchema])
def get_printers(db: Session = Depends(get_db)):
    return db.query(Printer).all()

@app.get("/debug/printers-count")
def count_printers(db: Session = Depends(get_db)):
    return {"count": db.query(Printer).count()}


@app.get("/printers/view", response_class=HTMLResponse)
def view_printers(request: Request, db: Session = Depends(get_db)):
    printers = db.query(Printer).all()
    for printer in printers:
        print(printer.user)
        if printer.toner_model:
            for consumable in printer.toner_model.consumables:
                if consumable.snipeit_asset_id:
                    consumable.stock = get_stock(snipeconn, consumable.snipeit_asset_id)
                else:
                    consumable.stock = "N/A"
    return templates.TemplateResponse("printers.html", {"request": request, "printers": printers})


def get_stock(snipeconn: snipeit.SnipeConnect, asset_id: str):
    try:
        response = snipeconn.consumables_stock(asset_id)
        data = json.loads(response)
        # Adjust the following to match your actual API structure.
        stock = data.get("remaining", "N/A")
        return stock
    except Exception as e:
        print(f"Error getting stock for asset {asset_id}: {str(e)}")
        return "Error"

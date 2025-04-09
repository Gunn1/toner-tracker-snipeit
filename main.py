from fastapi import FastAPI, Depends, HTTPException, Request
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
    type = Column(String)  # e.g. "Drum", "Fuser", "Waste Toner Box"
    part_number = Column(String)
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


snipeconn = snipeit.SnipeConnect(SNIPEIT_API_KEY,SNIPEIT_BASE_URL)
def sync_printers_from_snipeit(snipeconn: snipeit.SnipeConnect, db: Session):
    # Optional: Predefined consumables by printer model
    PREDEFINED_CONSUMABLES = {
        "HP Color LaserJet M255dw": [
        {
            "name": "HP 206X High Yield Black Original LaserJet Toner Cartridge",
            "type": "Toner",
            "part_number": "W2110X"
        },
        {
            "name": "HP 206X High Yield Magenta Original LaserJet Toner Cartridge",
            "type": "Toner",
            "part_number": "W2113X"
        },
        {
            "name": "HP 206X High Yield Cyan Original LaserJet Toner Cartridge",
            "type": "Toner",
            "part_number": "W2111X"
        },
        {
            "name": "HP 206X High Yield Yellow Original LaserJet Toner Cartridge",
            "type": "Toner",
            "part_number": "W2112X"
        }
    ],
        "HP LaserJet P2055dn": [
            {"name": "Maintenance Kit", "type": "Kit", "part_number": "CE255A-KIT"}
        ]
    }

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
    return templates.TemplateResponse("printers.html", {
        "request": request,
        "printers": printers
    })
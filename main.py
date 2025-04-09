from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from dotenv import load_dotenv
import requests
import os

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

# Models
class TonerModel(Base):
    __tablename__ = "toner_models"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    printer_model = Column(String)
    color = Column(String)
    part_number = Column(String)

class TonerStock(Base):
    __tablename__ = "toner_stock"
    id = Column(Integer, primary_key=True, index=True)
    toner_model_id = Column(Integer, ForeignKey("toner_models.id"))
    quantity = Column(Integer)
    restock_threshold = Column(Integer)

    model = relationship("TonerModel")

class Printer(Base):
    __tablename__ = "printers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
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

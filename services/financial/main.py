import base64
import hashlib
import os
import sys
import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from io import BytesIO

import httpx
import pytesseract
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Request, status
from fastapi.responses import JSONResponse
from PIL import Image
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session, select, create_engine, SQLModel

# Add shared directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from shared.models import Transaction, ReceiptItem, Budget, Goal, IngestedDocument
from shared.utils.ocr import preprocess_image_for_ocr, parse_receipt_items, categorize_finance_item
from shared.config import get_service_url
from shared.utils.persona import get_quip
from autonomy import check_budgets

# Database setup
_default_db_path = Path(os.getenv("FINANCIAL_DB_PATH", "/tmp/kilo_financial.db"))
_default_db_path.parent.mkdir(parents=True, exist_ok=True)
db_url = os.getenv("DATABASE_URL", f"sqlite:///{_default_db_path}")
engine = create_engine(db_url, connect_args={"check_same_thread": False})

app = FastAPI(title="Kilo Financial Service - Gremlin Edition 😈")

@app.get("/health")
def health():
    return {"status": "ok", "message": "I'm keeping an eye on your shiny gold coins! 💰"}

@app.get("/")
def list_transactions():
    """List all transactions. I'm counting your pennies! 🪙"""
    with Session(engine) as session:
        return session.exec(select(Transaction)).all()

@app.get("/budgets/status")
def list_budget_status():
    """Autonomous budget status check with Gremlin flavor."""
    status = check_budgets(engine)
    over = [b for b in status if b["over_budget"]]
    message = get_quip("budget_warning") if over else get_quip("budget_ok")
    return {
        "budgets": status,
        "gremlin_message": message
    }

@app.post("/")
def add_transaction(tx: Transaction, background_tasks: BackgroundTasks):
    tx.category = tx.category or _tx_categorize_item(tx.description or "")
    if tx.amount is not None:
        tx.transaction_type = "income" if tx.amount >= 0 else "expense"
    with Session(engine) as session:
        session.add(tx)
        session.commit()
        session.refresh(tx)
    return {
        "transaction": tx,
        "gremlin_message": f"Logged {tx.amount} for {tx.description}. Spending money is fun, isn't it? 💸"
    }

@app.delete("/transaction/{tx_id}")
def delete_transaction(tx_id: int):
    """Delete a transaction. It never happened! 🤫"""
    with Session(engine) as session:
        tx = session.get(Transaction, tx_id)
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found! I didn't hide it, I swear! 😇")
        session.delete(tx)
        session.commit()
        return {"message": f"Hehehe! I've shredded the evidence of that {tx.amount} purchase! ✂️"}

@app.delete("/budget/{budget_id}")
def delete_budget(budget_id: int):
    """Delete a budget. Freedom! 🕊️"""
    with Session(engine) as session:
        b = session.get(Budget, budget_id)
        if not b:
            raise HTTPException(status_code=404, detail="Budget not found! Maybe you never had one? 🤷‍♂️")
        session.delete(b)
        session.commit()
        return {"message": f"No more limits on '{b.category}'! Go wild! 😈"}

@app.delete("/goal/{goal_id}")
def delete_goal(goal_id: int):
    """Delete a goal. Giving up is easy! 😉"""
    with Session(engine) as session:
        g = session.get(Goal, goal_id)
        if not g:
            raise HTTPException(status_code=404, detail="Goal not found! I didn't steal it! 🤥")
        session.delete(g)
        session.commit()
        return {"message": f"Goal '{g.name}' has been tossed into the digital abyss! 🕳️"}

def _tx_categorize_item(name: str) -> str:
    lowered = (name or "").lower()
    mapping = [
        ("coffee", ["starbucks", "latte", "coffee"]),
        ("electronics", ["electronics", "tv", "laptop"]),
        ("transport", ["uber", "lyft", "trip", "taxi"]),
    ]
    for cat, keys in mapping:
        if any(k in lowered for k in keys):
            return cat
    return "miscellaneous"

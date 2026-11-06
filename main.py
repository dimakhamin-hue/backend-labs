import datetime
import os
import sqlite3
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="Учёт расходов")

DB_PATH = os.getenv("DB_PATH", "budget.db")


def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def query(sql, params=()):
    con = connect()
    rows = [dict(r) for r in con.execute(sql, params).fetchall()]
    con.close()
    return rows


def execute(sql, params=()):
    con = connect()
    cur = con.execute(sql, params)
    con.commit()
    con.close()
    return cur.lastrowid


# схема создаётся из файла schema.sql при старте
con = connect()
con.executescript(open("schema.sql", encoding="utf-8").read())
con.close()


class CategoryIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1)
    monthly_limit: float = Field(ge=0)
    note: str = ""


class CategoryPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: Optional[str] = Field(None, min_length=1)
    monthly_limit: Optional[float] = Field(None, ge=0)
    note: Optional[str] = None


class ExpenseIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    amount: float = Field(gt=0)
    date: datetime.date
    comment: str = ""


@app.exception_handler(RequestValidationError)
async def on_validation_error(request, exc):
    e = exc.errors()[0]
    names = [p for p in e["loc"] if isinstance(p, str) and p not in ("body", "query")]
    return JSONResponse(
        status_code=400,
        content={"error": e["msg"], "field": names[-1] if names else None},
    )


def find_category(id: int):
    rows = query("SELECT * FROM categories WHERE id = ?", (id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    return rows[0]


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- Категории ----------

@app.post("/api/categories", status_code=201)
def create_category(data: CategoryIn):
    new_id = execute(
        "INSERT INTO categories (name, monthly_limit, note) VALUES (?, ?, ?)",
        (data.name, data.monthly_limit, data.note),
    )
    return find_category(new_id)


@app.get("/api/categories")
def list_categories(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    name: Optional[str] = None,
    sort: str = "id",
    q: Optional[str] = None,
):
    column = sort.lstrip("-")
    if column not in ("id", "name", "monthly_limit"):
        return JSONResponse(status_code=400, content={"error": "Нельзя сортировать по этому полю", "field": "sort"})
    direction = "DESC" if sort.startswith("-") else "ASC"

    where = []
    params = []
    if name is not None:
        where.append("name = ?")
        params.append(name)
    if q is not None:
        where.append("name LIKE ?")
        params.append(f"%{q}%")
    sql = "SELECT * FROM categories"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {column} {direction} LIMIT ? OFFSET ?"
    params += [limit, offset]
    return query(sql, params)


@app.get("/api/categories/{id}")
def get_category(id: int):
    return find_category(id)


@app.patch("/api/categories/{id}")
def update_category(id: int, data: CategoryPatch):
    find_category(id)
    fields = data.model_dump(exclude_unset=True, exclude_none=True)
    if fields:
        sets = ", ".join(f"{k} = ?" for k in fields)
        execute(f"UPDATE categories SET {sets} WHERE id = ?", [*fields.values(), id])
    return find_category(id)


@app.delete("/api/categories/{id}", status_code=204)
def delete_category(id: int):
    find_category(id)
    execute("DELETE FROM categories WHERE id = ?", (id,))   # траты удаляются каскадом
    return Response(status_code=204)


# ---------- Траты ----------

@app.post("/api/categories/{id}/expenses", status_code=201)
def create_expense(id: int, data: ExpenseIn):
    category = find_category(id)
    date = str(data.date)
    month = date[:7]   # "2026-10"

    con = connect()
    try:
        con.execute("BEGIN IMMEDIATE")   # транзакция: проверка лимита и вставка вместе
        spent = con.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE category_id = ? AND substr(date, 1, 7) = ?",
            (id, month),
        ).fetchone()[0]
        if spent + data.amount > category["monthly_limit"]:
            raise HTTPException(status_code=409, detail="Превышен месячный лимит категории")
        cur = con.execute(
            "INSERT INTO expenses (category_id, amount, date, comment) VALUES (?, ?, ?, ?)",
            (id, data.amount, date, data.comment),
        )
        con.commit()
        new_id = cur.lastrowid
    finally:
        con.close()

    return {"id": new_id, "category_id": id, "amount": data.amount, "date": date, "comment": data.comment}


@app.get("/api/categories/{id}/expenses")
def list_expenses(id: int):
    find_category(id)
    return query("SELECT * FROM expenses WHERE category_id = ? ORDER BY date", (id,))


# ---------- Статистика ----------

@app.get("/api/expenses/stats")
def stats():
    return query(
        "SELECT substr(date, 1, 7) AS month, SUM(amount) AS total, COUNT(*) AS count "
        "FROM expenses GROUP BY month ORDER BY month"
    )
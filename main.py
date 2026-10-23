from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="Учёт расходов")

categories = {}
next_id = 1


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


@app.exception_handler(RequestValidationError)
async def on_validation_error(request, exc):
    e = exc.errors()[0]
    names = [p for p in e["loc"] if isinstance(p, str) and p not in ("body", "query")]
    return JSONResponse(
        status_code=400,
        content={"error": e["msg"], "field": names[-1] if names else None},
    )


def find(id: int):
    if id not in categories:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    return categories[id]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/categories", status_code=201)
def create_category(data: CategoryIn):
    global next_id
    category = {"id": next_id, **data.model_dump()}
    categories[next_id] = category
    next_id += 1
    return category


@app.get("/api/categories")
def list_categories(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    name: Optional[str] = None,
):
    items = list(categories.values())
    if name is not None:
        items = [c for c in items if c["name"] == name]
    return items[offset:offset + limit]


@app.get("/api/categories/{id}")
def get_category(id: int):
    return find(id)


@app.patch("/api/categories/{id}")
def update_category(id: int, data: CategoryPatch):
    category = find(id)
    category.update(data.model_dump(exclude_unset=True, exclude_none=True))
    return category


@app.delete("/api/categories/{id}", status_code=204)
def delete_category(id: int):
    find(id)
    del categories[id]
    return Response(status_code=204)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import restaurants, events, recommendations

app = FastAPI(title="FoodFlow API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(restaurants.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")
app.include_router(recommendations.router, prefix="/api/v1")

@app.get("/health")
async def health():
    return {"status": "ok"}

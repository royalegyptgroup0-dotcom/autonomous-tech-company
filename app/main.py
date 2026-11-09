from fastapi import FastAPI

app = FastAPI(
    title="Independent Technology Company API",
    version="0.1.0",
    description="A clean, independent API foundation. No customer data is accepted yet.",
)

@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "service": "company-api", "version": "0.1.0"}

@app.get("/", tags=["system"])
async def root():
    return {
        "service": "Independent Technology Company API",
        "status": "foundation",
        "docs": "/docs",
    }

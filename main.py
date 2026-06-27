from fastapi import FastAPI

from app.api.routes import deriv
from app.api.deps import deriv_service

app = FastAPI()


@app.on_event("startup")
async def startup():
    await deriv_service.connect()


@app.on_event("shutdown")
async def shutdown():
    await deriv_service.disconnect()


app.include_router(deriv.router, prefix="/deriv", tags=["deriv"])
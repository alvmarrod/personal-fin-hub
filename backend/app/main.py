from fastapi import FastAPI

app = FastAPI(title="Personal Fin Hub API")

@app.get("/")
async def root():
    return {"message": "Personal Fin Hub API is running"}

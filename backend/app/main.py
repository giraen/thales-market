from fastapi import FastAPI

app = FastAPI()

@app.get('/')
def check_status():
    return {"status": "ok"}
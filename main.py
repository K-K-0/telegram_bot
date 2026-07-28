import os

if "GOOGLE_APPLICATION_CREDENTIALS_JSON" in os.environ:
    creds_path = "/tmp/gcs-key.json"
    with open(creds_path, "w") as f:
        f.write(os.environ["GOOGLE_APPLICATION_CREDENTIALS_JSON"])
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path

import json, httpx
from fastapi import FastAPI, Request
from agent import run_agent
from logger import RunLogger

app = FastAPI()

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

CHAT_HISTORY: dict[int, list[str]] = {}

@app.post('/webhook')
async def telegram_webhook(request: Request):
    update = await request.json()
    message = update.get("message")

    if not message or "text" not in message:
        return {"ok": True}

    chat_id = message["chat"]["id"]
    text    = message["text"]         

    history = CHAT_HISTORY.setdefault(chat_id, [])
    history.append(text)

    logger = RunLogger(chat_id)
    logger.log("received_message", {"text": text, "history_len": len(history)})

    try:
        result_json_str = await run_agent(history, logger)
    except Exception as e:
        logger.log("error", {"error": str(e)})
        result_json_str = json.dumps({"answer": None, "log_url": "PENDING"})

    log_url = logger.finalize_and_upload()   

    try:
        parsed = json.loads(result_json_str)   
        parsed["log_url"] = log_url
        result_json_str = json.dumps(parsed)   
    except Exception as e:
        logger.log("error", {"error": f"final json parse failed: {e}"})

    await send_telegram_message(chat_id, result_json_str)
    return {"ok": True}                        


async def send_telegram_message(chat_id: int, text: str):
    async with httpx.AsyncClient() as client:   
        await client.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": text
        })


@app.get('/')
async def health():
    return {"status": "alive"}
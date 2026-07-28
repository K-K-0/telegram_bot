import httpx, io, contextlib, traceback
import pandas as pd, numpy as np

async def web_fetch(url: str) -> str:
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        r = await client.get(url)
        return r.text[:20000]

def run_python(code: str) -> str:
    buf = io.StringIO()
    local_var = {"pd": pd, "np": np}
    try:
        with contextlib.redirect_stdout(buf):
            exec(code, {}, local_var)
    except Exception:
        return f"ERROR:\n{traceback.format_exc()}"

    return buf.getvalue() or str(local_var.get("result", ""))

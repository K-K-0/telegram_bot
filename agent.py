import os, json, re
from openai import OpenAI
from tools import web_fetch, run_python

client = OpenAI(
    api_key=os.environ["AIPIPE_TOKEN"],
    base_url="https://aipipe.org/openai/v1"
)

MODEL = "gpt-4o-mini"  

SYSTEM_PROMPT = """You are a data analysis agent. You will be given a conversation
with a user; answer their LAST message only, using earlier messages as context.

You have tools:
- web_fetch(url): fetch a public webpage/dataset (CSV, JSON, HTML)
- run_python(code): execute Python to compute/clean/analyze data (pandas, numpy available)

The final user message will specify EXACTLY what JSON shape to reply with, e.g.
{"answer": {...}, "log_url": "..."}.
You must extract that exact shape from their instructions, fill in "answer" with your
computed result, and leave "log_url" as a placeholder string "LOG_URL_PLACEHOLDER" —
the system will substitute the real log URL afterward.

Reply with ONLY the raw JSON object matching their requested shape. No markdown, no
commentary, no code fences.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch a public URL (dataset, webpage, CSV/JSON) and return its content.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": "Execute Python code (pandas/numpy available) and return stdout.",
            "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"]
            }
        }
    }
]

async def run_agent(history: list[str], logger) -> str:
    conversation = "\n".join(f"[msg {i+1}] {m}" for i, m in enumerate(history))
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": conversation}
    ]

    for step in range(8):
        resp = client.chat.completions.create(
            model=MODEL,
            max_tokens=2000,
            messages=messages,
            tools=TOOLS,
        )
        choice = resp.choices[0]
        logger.log("llm_response", {
            "finish_reason": choice.finish_reason,
            "message": choice.message.model_dump()
        })

        msg = choice.message

        if not msg.tool_calls:
            text = extract_json(msg.content or "")
            logger.log("final_answer", {"raw": text})
            return text

        # append assistant turn (with tool calls) to history
        messages.append(msg.model_dump(exclude_none=True))

        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            if tc.function.name == "web_fetch":
                result = await web_fetch(args["url"])
            elif tc.function.name == "run_python":
                result = run_python(args["code"])
            else:
                result = "unknown tool"

            logger.log("tool_call", {
                "tool": tc.function.name,
                "input": args,
                "output": str(result)[:3000]
            })

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": str(result)[:8000]
            })

    logger.log("error", {"error": "max steps exceeded"})
    return json.dumps({"answer": None, "log_url": "LOG_URL_PLACEHOLDER"})


def extract_json(text: str) -> str:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group(0) if match else text
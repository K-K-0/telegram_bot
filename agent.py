import os, json, re
from anthropic import Anthropic
from tools import web_fetch, run_python

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

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
        "name": "web_fetch",
        "description": "Fetch a public URL (dataset, webpage, CSV/JSON) and return its content.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"]
        }
    },
    {
        "name": "run_python",
        "description": "Execute Python code (pandas/numpy available) and return stdout.",
        "input_schema": {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"]
        }
    }
]


async def run_agent(history: list[str], logger) -> str:
    conversation = "\n".join(f"[msg {i+1}] {m}" for i, m in enumerate(history))
    messages     = [{"role": "user", "content": conversation}]

    for step in range(8):
        resp = client.messages.create(
            model="claude-fable-5",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=TOOLS
        )
        logger.log("llm_response", { "stop_reason": resp.stop_reason, "content": [b.model_dump for b in resp.content]})

        if resp.stop_reason != "tool_use":
            # extract final text, should be pure JSON
            text = "".join(b.text for b in resp.content if b.type == "text")
            text = extract_json(text)
            logger.log("final_answer", {"raw": text})
            return text

        messages.append({"role": "assistant", "content": resp.content})

        tools_result = []

        for block in resp.content:
            if block.type == "tool_use":
                if block.name == "web_fetch":
                    result = await web_fetch(block.input['url'])
                elif block.name == "run_python":
                    result = await run_python(block.input['code'])
                else:
                    result = "unknown tool"
                logger.log("tool_call", {"tool": block.name, "input": block.input, "output": str(result)[:3000]})

                tools_result.append({
                    "type": "tool_result",
                    "tool_user_id": block.id,
                    "content": str(result)[:8000]
                })
        messages.append({"role": "user", "content": tools_result})

    logger.log("error", {"error": "max steps exceeded"})
    return json.dumps({"answer": None, "log_url": "LOG_URL_PLACEHOLDER"})

def extract_json(text: str) -> str:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group(0) if match else text

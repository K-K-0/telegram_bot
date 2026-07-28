import json, time, os, uuid, httpx

class RunLogger:

    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.run_id = f"{chat_id}-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        self.lines = []

    def log(self, event, data):
        self.lines.append(json.dumps({"ts": time.time(), "event": event, **data}))

    def finalize_and_upload(self) -> str:
        content = "\n".join(self.lines)
        # Example: upload to a GCS bucket you made public (like task 1!)
        url = upload_to_gcs(f"logs/{self.run_id}.jsonl", content)
        return url

    def public_url(self):
        return f"https://storage.googleapis.com/YOUR_BUCKET/logs/{self.run_id}.jsonl"


def upload_to_gcs(path, content):
    from google.cloud import storage

    client = storage.Client()
    bucket = client.bucket(os.environ['LOG_BUCKET'])
    blob = bucket.blob(path)
    blob.upload_from_string(content, content_type='application/x-ndjson')
    blob.make_public()
    return blob.public_url
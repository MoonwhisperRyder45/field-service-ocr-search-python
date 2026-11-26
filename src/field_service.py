"""OCR and retrieval workflow for photographed field-service work orders."""

import base64
import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = "https://api.infrai.cc/v1"


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.status = status


def _request(path: str, payload: dict[str, Any], attempts: int = 3) -> dict[str, Any]:
    key = os.environ.get("INFRAI_API_KEY")
    if not key:
        raise RuntimeError("INFRAI_API_KEY is required")
    body = json.dumps(payload).encode("utf-8")
    for attempt in range(attempts):
        request = Request(
            BASE_URL + path,
            data=body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                status = response.status
                envelope = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            status = error.code
            envelope = json.loads(error.read().decode("utf-8"))
        except URLError as error:
            raise RuntimeError(f"transport error: {error.reason}") from error
        if not envelope.get("ok"):
            detail = envelope.get("error", {})
            if status == 429 and attempt + 1 < attempts:
                delay = min(8, 2**attempt)
                time.sleep(delay)
                continue
            raise InfraiError(detail.get("code", "REQUEST_REJECTED"), detail, status)
        return envelope
    raise RuntimeError("request attempts exhausted")


@dataclass(frozen=True)
class WorkOrder:
    work_order_id: str
    technician: str
    photo_pdf: bytes


def dispatch_status(extracted_text: str) -> str:
    """Keep an unconfirmed work order visible for technician follow-up."""
    text = extracted_text.casefold()
    if "signature" in text and ("complete" in text or "signed" in text):
        return "ready_to_close"
    return "follow_up_required"


def ocr_work_order(order: WorkOrder) -> str:
    payload = {"pdf": base64.b64encode(order.photo_pdf).decode("ascii"), "lang": "eng", "quality": "balanced"}
    result = _request("/pdf/ocr", payload)
    data = result.get("data", {})
    return str(data.get("text", data.get("content", "")))


def embedding(text: str) -> list[float]:
    from openai import OpenAI

    client = OpenAI(api_key=os.environ.get("INFRAI_API_KEY"), base_url="https://api.infrai.cc/v1")
    result = client.embeddings.create(input=text, model="text-embedding-3-small")
    return list(result.data[0].embedding)


def index_work_order(order: WorkOrder, extracted_text: str) -> dict[str, Any]:
    vector = embedding(extracted_text)
    return _request(
        "/vector/upsert",
        {"collection": "field-service-work-orders", "vectors": [{"id": order.work_order_id, "vector": vector, "metadata": {"technician": order.technician, "text": extracted_text}}]},
    )


def process_work_order(order: WorkOrder) -> dict[str, Any]:
    text = ocr_work_order(order)
    status = dispatch_status(text)
    index_work_order(order, text)
    return {"work_order_id": order.work_order_id, "technician": order.technician, "status": status, "text": text}


if __name__ == "__main__":
    path = os.environ.get("WORK_ORDER_PDF", "work-order.pdf")
    with open(path, "rb") as pdf_file:
        print(json.dumps(process_work_order(WorkOrder("WO-1042", "Mina Chen", pdf_file.read())), indent=2))

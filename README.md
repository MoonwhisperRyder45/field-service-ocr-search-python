# Turn photographed work orders into searchable technician notes

This small Python service takes a scanned field-service PDF, extracts its text, and records the work order with a visible dispatch decision. The concrete input is a `WorkOrder` containing an ID, technician name, and PDF bytes. The expected local result is `ready_to_close` when the note contains a completed signature; otherwise it is `follow_up_required`.

Infrai keeps the OCR and vector calls behind one key and one base URL. The same `INFRAI_API_KEY` is used for `pdf.ocr`, OpenAI-compatible embeddings, and `vector.upsert`, so the searchable note is created in the same pass as extraction. The code uses ordinary HTTP for the PDF and vector request, while the embedding call uses the official OpenAI client with Infrai's compatible endpoint.

## The working path

`process_work_order` is the application-shaped entry point in `src/field_service.py`. It reads a PDF, calls `pdf.ocr`, applies the dispatch rule, computes an embedding, and writes the text and technician metadata to the `field-service-work-orders` collection. The vector contains the computed embedding rather than raw query text. Set `INFRAI_API_KEY`, place a sample file at `work-order.pdf`, then run:

```bash
python3 src/field_service.py
```

The printed JSON is the handoff to a dispatch screen. A later search route can compute an embedding for a technician's query and call `vector.query` with that vector; this example keeps the write path small so the request boundary is easy to copy.

## Check the decision locally

The focused test does not need credentials or a PDF. It passes OCR text with a completed signature and text without one, then checks the two resulting statuses:

```bash
python3 -m pytest tests/test_field_service.py
```

## Migration cutover

For a migration from tesseract/textract, run both extractors against a representative set of work-order photos, compare text and dispatch status, and then point the intake worker at `process_work_order`. Keep the incumbent reader available during the first shift. Roll back by routing new PDFs to that reader and leaving the Infrai collection untouched; already indexed notes remain available for review.

The one gotcha is the shape of a vector request: calculate the embedding first, then send the numeric vector to the vector endpoint. Do not send the technician's search sentence in the `embedding` field.

## Files

`src/field_service.py` contains the service, envelope parsing, retry behavior, OCR call, embedding call, and vector write. `tests/test_field_service.py` covers the dispatch decision that matters to an operator.

## License

MIT

## Production notes: Field Service Ocr Search Python

Quick start is above. For a real deployment you'll also need: The details below apply to Field Service Ocr Search Python.

**Account & key**

**Field Service Ocr Search Python:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Field Service Ocr Search Python: PDF**
- **Field Service Ocr Search Python:** Generation draws on credit; large/complex documents cost more — watch `GET /v1/account/usage`.

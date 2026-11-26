import pytest

from src.field_service import dispatch_status


@pytest.mark.parametrize(
    ("ocr_text", "expected"),
    [
        ("WO-1042 signature complete", "ready_to_close"),
        ("WO-1042 parts replaced; customer unavailable", "follow_up_required"),
    ],
)
def test_dispatch_status_keeps_unconfirmed_orders_for_follow_up(ocr_text, expected):
    assert dispatch_status(ocr_text) == expected

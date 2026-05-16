import os
import pytest
import tempfile

import db


@pytest.fixture(autouse=True)
def tmp_db(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_FILE", str(tmp_path / "test.db"))
    db.init_db()


def _msg(channel="test_ch", date="2026-05-16T10:00:00+00:00", text="тривога"):
    return {"channel": channel, "date": date, "text": text}


def test_save_and_count():
    saved = db.save_messages([_msg()])
    assert saved == 1
    assert db.count_messages() == 1


def test_duplicate_not_saved():
    msg = _msg()
    db.save_messages([msg])
    saved = db.save_messages([msg])
    assert saved == 0
    assert db.count_messages() == 1


def test_save_multiple():
    msgs = [_msg(date=f"2026-05-16T{h:02d}:00:00+00:00") for h in range(5)]
    saved = db.save_messages(msgs)
    assert saved == 5


def test_get_messages_since():
    db.save_messages([
        _msg(date="2026-05-16T10:00:00+00:00", text="старе"),
        _msg(date="2099-01-01T10:00:00+00:00", text="майбутнє"),
    ])
    results = db.get_messages_since(hours=1)
    texts = [m["text"] for m in results]
    assert "майбутнє" in texts
    assert "старе" not in texts


def test_get_messages_fields():
    db.save_messages([_msg(channel="ch1", text="текст")])
    msgs = db.get_messages_since(hours=999)
    assert msgs[0]["channel"] == "ch1"
    assert msgs[0]["text"] == "текст"
    assert "date" in msgs[0]


def test_get_messages_sorted():
    db.save_messages([
        _msg(date="2099-01-01T12:00:00+00:00"),
        _msg(date="2099-01-01T10:00:00+00:00"),
        _msg(date="2099-01-01T11:00:00+00:00"),
    ])
    msgs = db.get_messages_since(hours=999)
    dates = [m["date"] for m in msgs]
    assert dates == sorted(dates)

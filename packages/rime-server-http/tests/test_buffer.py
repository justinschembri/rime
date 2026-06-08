"""Unit tests for the in-memory buffer."""

import pytest

from rime_server_http.buffer import AppBuffer, MessageBuffer, StoredMessage


def _msg(**kwargs) -> StoredMessage:
    return StoredMessage(app_id="test-app", **kwargs)


class TestAppBuffer:
    def test_enqueue_and_depth(self):
        buf = AppBuffer(app_id="a", max_depth=3)
        assert buf.enqueue(_msg())
        assert buf.enqueue(_msg())
        assert buf.depth == 2

    def test_enqueue_rejects_when_full(self):
        buf = AppBuffer(app_id="a", max_depth=2)
        assert buf.enqueue(_msg())
        assert buf.enqueue(_msg())
        assert not buf.enqueue(_msg())
        assert buf.depth == 2

    def test_drain_moves_to_in_flight(self):
        buf = AppBuffer(app_id="a")
        m1, m2, m3 = _msg(), _msg(), _msg()
        buf.enqueue(m1)
        buf.enqueue(m2)
        buf.enqueue(m3)

        batch = buf.drain(2)
        assert len(batch) == 2
        assert batch[0].id == m1.id
        assert batch[1].id == m2.id
        assert buf.depth == 1
        assert buf.in_flight_count == 2

    def test_drain_respects_limit_larger_than_queue(self):
        buf = AppBuffer(app_id="a")
        buf.enqueue(_msg())
        assert len(buf.drain(100)) == 1

    def test_drain_empty_queue_returns_empty(self):
        buf = AppBuffer(app_id="a")
        assert buf.drain(10) == []

    def test_ack_removes_from_in_flight(self):
        buf = AppBuffer(app_id="a")
        m1, m2 = _msg(), _msg()
        buf.enqueue(m1)
        buf.enqueue(m2)
        buf.drain(2)

        unknown = buf.ack([m1.id])
        assert unknown == []
        assert buf.in_flight_count == 1
        assert m2.id in buf.in_flight

    def test_ack_returns_unknown_ids(self):
        buf = AppBuffer(app_id="a")
        unknown = buf.ack(["does-not-exist"])
        assert unknown == ["does-not-exist"]

    def test_ack_all_clears_in_flight(self):
        buf = AppBuffer(app_id="a")
        m1, m2 = _msg(), _msg()
        buf.enqueue(m1)
        buf.enqueue(m2)
        batch = buf.drain(2)
        buf.ack([m.id for m in batch])
        assert buf.in_flight_count == 0

    def test_fifo_order_preserved(self):
        buf = AppBuffer(app_id="a")
        msgs = [_msg(body=str(i).encode()) for i in range(5)]
        for m in msgs:
            buf.enqueue(m)
        drained = buf.drain(5)
        assert [m.id for m in drained] == [m.id for m in msgs]


class TestMessageBuffer:
    def test_get_or_create_creates_new(self):
        mb = MessageBuffer(max_depth_per_app=10)
        buf = mb.get_or_create("app-a")
        assert buf.app_id == "app-a"

    def test_get_or_create_returns_same(self):
        mb = MessageBuffer()
        b1 = mb.get_or_create("app-a")
        b2 = mb.get_or_create("app-a")
        assert b1 is b2

    def test_stats(self):
        mb = MessageBuffer()
        mb.get_or_create("app-a").enqueue(_msg())
        mb.get_or_create("app-a").enqueue(_msg())
        mb.get_or_create("app-b").enqueue(_msg())
        s = mb.stats()
        assert s["app-a"]["pending"] == 2
        assert s["app-b"]["pending"] == 1

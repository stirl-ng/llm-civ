from orchestrator.engine import OrchestratorEngine
import json


def test_ping_reply():
    eng = OrchestratorEngine()
    resp = eng.handle_message(b'{"kind":"ping","n":1}')
    assert resp is not None
    obj = json.loads(resp.decode("utf-8"))
    assert obj["kind"] == "pong"
    assert obj["server"] == "orchestrator"
    assert obj["echo"]["kind"] == "ping"


def test_non_ping_no_reply():
    eng = OrchestratorEngine()
    assert eng.handle_message(b'{"kind":"other"}') is None


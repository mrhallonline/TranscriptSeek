import io
import json

from transcriptseek.ipc import serve


def test_health_and_version_rejection() -> None:
    incoming = io.StringIO(
        json.dumps({"id": 1, "version": 1, "action": "health"}) + "\n"
        + json.dumps({"id": 2, "version": 99, "action": "health"}) + "\n"
    )
    outgoing = io.StringIO()
    serve(incoming, outgoing)
    responses = [json.loads(line) for line in outgoing.getvalue().splitlines()]
    assert responses[0]["result"]["network"] == "disabled"
    assert responses[1]["ok"] is False


from transcriptseek.analyzers import ANALYZERS, AnalyzerContext


CONTEXT = AnalyzerContext(
    project_id="project_test",
    transcript_hash="abc",
    segments=[
        {"id": "one", "start_ms": 0, "text": "Trust and care support a safe neighborhood."},
        {"id": "two", "start_ms": 1000, "text": "The neighborhood meeting built trust and shared ownership."},
    ],
)


def test_all_builtin_analyzers_are_local_and_traceable() -> None:
    assert {"frequency", "collocation", "keyphrase", "concordance", "entity", "sentiment", "topic_explorer"} <= ANALYZERS.keys()
    for analyzer in ANALYZERS.values():
        parameters = {"term": "trust"} if analyzer.analyzer_id == "concordance" else {}
        result = analyzer.run(CONTEXT, parameters)
        assert isinstance(result, dict)
        assert analyzer.manifest()["limitations"]

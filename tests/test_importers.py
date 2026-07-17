from transcriptseek.importers import parse_csv_transcript, parse_json, parse_srt, parse_vtt


def test_srt_and_vtt_timestamps() -> None:
    srt = "1\n00:00:01,250 --> 00:00:03,500\nHello world\n"
    vtt = "WEBVTT\n\n00:00:01.250 --> 00:00:03.500\nHello world\n"
    assert parse_srt(srt)[0].start_ms == 1250
    assert parse_vtt(vtt)[0].end_ms == 3500


def test_csv_mapping_and_json_milliseconds() -> None:
    segment = parse_csv_transcript("start,end,text,speaker\n1.5,2.0,Hello,A\n")[0]
    assert (segment.start_ms, segment.end_ms, segment.speaker) == (1500, 2000, "A")
    segment = parse_json('[{"start_ms": 125, "end_ms": 500, "text": "Hi"}]')[0]
    assert (segment.start_ms, segment.end_ms) == (125, 500)


from app.services.transcript_parser import parse_srt


def test_parse_srt_keeps_timestamps():
    data = parse_srt("1\n00:00:01,000 --> 00:00:03,000\n안녕하세요\n")
    assert data.segments[0].start == 1
    assert data.segments[0].end == 3
    assert data.segments[0].text == "안녕하세요"

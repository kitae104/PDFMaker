from app.services.youtube import clean_vtt
from app.services.transcript_parser import parse_vtt


def test_clean_vtt_removes_tags_and_entities():
    text = clean_vtt("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n<c>Paint &amp; color</c>\n")
    parsed = parse_vtt(text)
    assert parsed.segments[0].text == "Paint & color"

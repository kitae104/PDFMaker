from app.services.transcript_parser import parse_srt


def test_parse_srt_keeps_timestamps():
    data = parse_srt("1\n00:00:01,000 --> 00:00:03,000\n안녕하세요\n")
    assert data.segments[0].start == 1
    assert data.segments[0].end == 3
    assert data.segments[0].text == "안녕하세요"


def test_parse_srt_collapses_rolling_caption_repetition():
    data = parse_srt(
        "\n\n".join(
            [
                "1\n00:00:01,000 --> 00:00:02,000\n페인트 한 통",
                "2\n00:00:02,000 --> 00:00:03,000\n페인트 한 통 사서",
                "3\n00:00:03,000 --> 00:00:04,000\n사서 차에 뿌리면",
                "4\n00:00:04,000 --> 00:00:05,000\n차에 뿌리면 색이 입혀집니다",
            ]
        )
    )

    assert len(data.segments) == 1
    assert data.segments[0].text == "페인트 한 통 사서 차에 뿌리면 색이 입혀집니다"


def test_parse_srt_applies_common_caption_corrections():
    data = parse_srt("1\n00:00:01,000 --> 00:00:03,000\n알료와 청가제는 구착력과 강택에 영향을 줍니다\n")

    assert data.segments[0].text == "안료와 첨가제는 부착력과 광택에 영향을 줍니다"

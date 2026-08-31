from app.services.youtube import extract_youtube_id, normalize_watch_url


def test_extract_youtube_short_url_with_query():
    assert extract_youtube_id("https://youtu.be/JKj7eTi0Axo?si=AJrOgnxr5x_fSOlP") == "JKj7eTi0Axo"


def test_normalize_watch_url():
    assert normalize_watch_url("JKj7eTi0Axo") == "https://www.youtube.com/watch?v=JKj7eTi0Axo"

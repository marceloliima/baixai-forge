import pytest

from baixai_forge.platforms import InvalidMediaUrl, detect_platform, normalize_url


@pytest.mark.parametrize(
    ("url", "slug"),
    [
        ("youtu.be/abc", "youtube"),
        ("https://www.youtube.com/watch?v=abc", "youtube"),
        ("https://www.instagram.com/reel/abc/", "instagram"),
        ("https://www.tiktok.com/@u/video/123", "tiktok"),
        ("https://fb.watch/abc", "facebook"),
        ("https://shopee.com.br/product/1/2", "shopee"),
    ],
)
def test_detect_platform(url, slug):
    assert detect_platform(url).slug == slug


def test_normalize_removes_fragment():
    assert normalize_url("youtube.com/watch?v=x#fragment") == "https://youtube.com/watch?v=x"


@pytest.mark.parametrize("url", ["file:///etc/passwd", "https://example.com/video", "ftp://youtube.com/a"])
def test_reject_unsafe_or_unsupported(url):
    with pytest.raises(InvalidMediaUrl):
        detect_platform(url)

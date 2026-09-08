import json

import pytest

from baixai_forge.shopee import ShopeeResolutionError, clean_shopee_mp4_url, parse_shopee_share_html


ORIGINAL = (
    "https://down-zl-br.vod.susercontent.com/api/v4/11110124/mms/"
    "br-11110124-6kfkr-mddnoul12w4yc5.16003551755115279.9253.mp4"
)
CLEAN = (
    "https://down-zl-br.vod.susercontent.com/api/v4/11110124/mms/"
    "br-11110124-6kfkr-mddnoul12w4yc5.mp4"
)


def test_clean_shopee_mp4_url_removes_numeric_tokens():
    assert clean_shopee_mp4_url(ORIGINAL) == CLEAN


def test_clean_shopee_mp4_url_is_restricted_to_shopee_cdn():
    other = "https://example.com/video.16003551755115279.9253.mp4"
    assert clean_shopee_mp4_url(other) is None


def test_parse_next_data_extracts_media_metadata():
    next_data = {
        "props": {
            "pageProps": {
                "mediaInfo": {
                    "video": {
                        "watermarkVideoUrl": ORIGINAL,
                        "caption": "Oferta do dia",
                        "duration": 18018,
                    },
                    "userInfo": {"videoUserName": "descontaco.comm"},
                }
            }
        }
    }
    page = (
        '<html><head><meta property="og:title" content="Fallback title"></head><body>'
        f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>'
        '</body></html>'
    )
    media = parse_shopee_share_html(page, "https://sv.shopee.com.br/share-video/example")
    assert media.original_media_url == ORIGINAL
    assert media.title == "Oferta do dia"
    assert media.uploader == "descontaco.comm"
    assert media.duration == pytest.approx(18.018)


def test_parse_next_data_uses_og_title_when_caption_empty():
    next_data = {
        "props": {
            "pageProps": {
                "mediaInfo": {
                    "video": {"watermarkVideoUrl": ORIGINAL, "caption": "", "duration": 12000},
                    "userInfo": {"videoUserName": "seller"},
                }
            }
        }
    }
    page = (
        '<html><head><meta property="og:title" content="seller on Shopee Video"></head><body>'
        f'<script id="__NEXT_DATA__">{json.dumps(next_data)}</script>'
        '</body></html>'
    )
    media = parse_shopee_share_html(page, "https://sv.shopee.com.br/share-video/example")
    assert media.title == "seller on Shopee Video"


def test_parse_shopee_page_without_media_fails_cleanly():
    with pytest.raises(ShopeeResolutionError):
        parse_shopee_share_html("<html></html>", "https://sv.shopee.com.br/share-video/example")


def _settings(tmp_path):
    from baixai_forge.config import Settings

    data = tmp_path / "data"
    return Settings(
        app_name="Baixaí Forge",
        app_version="1.1.0",
        host="127.0.0.1",
        port=8765,
        base_dir=tmp_path,
        data_dir=data,
        download_dir=data / "downloads",
        log_dir=data / "logs",
        db_path=data / "db.sqlite3",
        max_concurrent_downloads=2,
        job_retries=1,
        retention_hours=72,
        socket_timeout_seconds=30,
        min_free_disk_mb=64,
        log_level="INFO",
        open_browser=False,
        allow_remote=False,
        cookies_file=None,
        cookies_browser=None,
        access_log=False,
    )


def _share_html():
    payload = {
        "props": {
            "pageProps": {
                "mediaInfo": {
                    "video": {"watermarkVideoUrl": ORIGINAL, "caption": "Oferta", "duration": 18018},
                    "userInfo": {"videoUserName": "descontaco.comm"},
                }
            }
        }
    }
    return f'<script id="__NEXT_DATA__">{json.dumps(payload)}</script>'


def test_resolver_follows_short_link_and_prefers_valid_clean_variant(tmp_path):
    import httpx
    import threading

    from baixai_forge.shopee import ShopeeResolver

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "br.shp.ee":
            return httpx.Response(302, headers={"Location": "https://sv.shopee.com.br/share-video/abc"})
        if request.url.host == "sv.shopee.com.br":
            return httpx.Response(200, text=_share_html())
        if str(request.url) == CLEAN:
            assert request.headers.get("range") == "bytes=0-0"
            return httpx.Response(206, content=b"x", headers={"Content-Type": "video/mp4"})
        raise AssertionError(f"unexpected request: {request.url}")

    resolver = ShopeeResolver(_settings(tmp_path), transport=httpx.MockTransport(handler))
    media = resolver.resolve("https://br.shp.ee/eo1q8p7f?fromSource=copy_link", threading.Event())
    assert media.page_url == "https://sv.shopee.com.br/share-video/abc"
    assert media.media_url == CLEAN
    assert media.clean_variant is True
    assert media.uploader == "descontaco.comm"


def test_resolver_falls_back_to_payload_url_when_clean_variant_is_missing(tmp_path):
    import httpx
    import threading

    from baixai_forge.shopee import ShopeeResolver

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "br.shp.ee":
            return httpx.Response(302, headers={"Location": "https://sv.shopee.com.br/share-video/abc"})
        if request.url.host == "sv.shopee.com.br":
            return httpx.Response(200, text=_share_html())
        if str(request.url) == CLEAN:
            return httpx.Response(404)
        raise AssertionError(f"unexpected request: {request.url}")

    resolver = ShopeeResolver(_settings(tmp_path), transport=httpx.MockTransport(handler))
    media = resolver.resolve("https://br.shp.ee/eo1q8p7f", threading.Event())
    assert media.media_url == ORIGINAL
    assert media.clean_variant is False


def test_resolver_blocks_redirect_outside_shopee_allowlist(tmp_path):
    import httpx
    import threading

    from baixai_forge.shopee import ShopeeResolutionError, ShopeeResolver

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "http://127.0.0.1/private"})

    resolver = ShopeeResolver(_settings(tmp_path), transport=httpx.MockTransport(handler))
    with pytest.raises(ShopeeResolutionError) as exc_info:
        resolver.resolve("https://br.shp.ee/eo1q8p7f", threading.Event())
    assert exc_info.value.code == "SHOPEE_REDIRECT_BLOCKED"

from baixai_forge.downloader import classify_error, parse_browser_cookie_spec


def test_cookie_browser_parser():
    assert parse_browser_cookie_spec("chrome") == ("chrome", None, None, None)
    assert parse_browser_cookie_spec("firefox:default::none") == ("firefox", "default", None, "none")


def test_error_classification_network_is_retryable():
    message, code, retryable = classify_error("ERROR: connection reset by peer")
    assert code == "NETWORK_ERROR"
    assert retryable is True
    assert message

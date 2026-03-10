from openvort.channels.feishu.channel import merge_streaming_text, truncate_summary


def test_merge_streaming_text_prefers_snapshot_growth():
    assert merge_streaming_text("hello", "hello world") == "hello world"


def test_merge_streaming_text_handles_overlap_delta():
    assert merge_streaming_text("a", "ab") == "ab"
    assert merge_streaming_text("ab", "bcdef") == "abcdef"


def test_merge_streaming_text_ignores_regression_snapshot():
    assert merge_streaming_text("complete output", "complete") == "complete output"


def test_truncate_summary_keeps_short_text():
    assert truncate_summary("short summary") == "short summary"

"""插件配置表单：有数字员工时给下拉，没有时退回手填。"""

from types import SimpleNamespace

from openvort.plugins.autodev import AutoDevPlugin


def _field(choices):
    p = AutoDevPlugin()
    p._svc = SimpleNamespace(member_choices=choices)
    schema = p.get_config_schema()
    assert len(schema) == 1
    return schema[0]


def test_picker_lists_virtual_members_and_marks_unbound():
    f = _field([{"id": "m1", "name": "实施专家", "node_id": "n1"},
                {"id": "m2", "name": "复盘员", "node_id": ""}])
    assert f["type"] == "select"
    assert f["options"] == [{"value": "m1", "label": "实施专家"},
                            {"value": "m2", "label": "复盘员（未绑定工作机）"}]


def test_falls_back_to_text_when_no_members():
    assert _field([])["type"] == "string"
    p = AutoDevPlugin()  # 快照未就绪（activate 之前）
    assert p.get_config_schema()[0]["type"] == "string"

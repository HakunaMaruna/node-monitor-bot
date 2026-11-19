from app.handlers.menu import parse_id
from app.models.node import Node
from app.utils.keyboards import (
    confirm_delete,
    main_inline,
    node_actions,
    nodes_list,
    protocol_choice,
    reply_menu,
    skip_choice,
)


def inline_data(markup) -> list[str]:
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def test_reply_menu_has_quick_actions():
    labels = [button.text for row in reply_menu().keyboard for button in row]
    assert "Список нод" in labels
    assert "Добавить ноду" in labels
    assert "Проверить все" in labels


def test_main_inline_callbacks():
    assert set(inline_data(main_inline())) == {"list", "add", "check_all"}


def test_nodes_list_uses_node_ids():
    node = Node(id=7, name="main", ip="10.0.0.1", port=80, protocol="HTTP", last_status=False)
    data = inline_data(nodes_list([node]))
    assert "node:7" in data
    assert "main" in [button.text for row in nodes_list([node]).inline_keyboard for button in row][0]
    assert "\n" in nodes_list([node]).inline_keyboard[0][0].text


def test_node_actions_toggle_label():
    enabled = Node(id=1, name="a", ip="1.1.1.1", port=1, protocol="TCP", enabled=True)
    disabled = Node(id=1, name="a", ip="1.1.1.1", port=1, protocol="TCP", enabled=False)
    assert "toggle:1" in inline_data(node_actions(enabled))
    assert "interval:1" in inline_data(node_actions(enabled))
    labels = [button.text for row in node_actions(enabled).inline_keyboard for button in row]
    assert "Выключить" in labels
    labels = [button.text for row in node_actions(disabled).inline_keyboard for button in row]
    assert "Включить" in labels


def test_wizard_keyboards():
    assert set(inline_data(protocol_choice())) == {
        "protocol:TCP", "protocol:HTTP", "protocol:HTTPS", "cancel"
    }
    assert set(inline_data(skip_choice("timeout"))) == {"skip:timeout", "cancel"}


def test_keyboard_rows_use_full_width():
    node = Node(id=1, name="a", ip="1.1.1.1", port=1, protocol="TCP")
    markups = [
        main_inline(),
        node_actions(node),
        nodes_list([node]),
        confirm_delete(1),
        protocol_choice(),
        skip_choice("timeout"),
    ]

    assert all(len(row) == 1 for markup in markups for row in markup.inline_keyboard)
    assert all(len(row) == 1 for row in reply_menu().keyboard)


def test_parse_id():
    assert parse_id("node:12", "node") == 12
    assert parse_id("node:x", "node") is None
    assert parse_id("bad", "node") is None
    assert parse_id("check:5", "node") is None

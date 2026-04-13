from __future__ import annotations

import pandas as pd
import pytest

import chat_service


def test_get_info_by_eids_accepts_single_string(monkeypatch: pytest.MonkeyPatch):
    gdf = pd.DataFrame(
        [
            {"EID": "RKD-1", "IME": "Prvi spomenik", "OBCINA": "Piran"},
            {"EID": "RKD-2", "IME": "Drugi spomenik", "OBCINA": "Izola"},
        ]
    )
    monkeypatch.setattr(chat_service, "_load_gdf", lambda: gdf)

    result = chat_service.get_info_by_eids("RKD-1", ["EID", "IME"])

    assert result == [{"EID": "RKD-1", "IME": "Prvi spomenik"}]


def test_get_info_by_eids_falls_back_to_esd(monkeypatch: pytest.MonkeyPatch):
    gdf = pd.DataFrame(
        [
            {"ESD": "4302", "EID": "1-27555", "IME": "Vrtec v Rižani", "OBCINA": "Koper"},
        ]
    )
    monkeypatch.setattr(chat_service, "_load_gdf", lambda: gdf)

    result = chat_service.get_info_by_eids("4302", ["EID", "IME"])

    assert result == [{"EID": "1-27555", "IME": "Vrtec v Rižani"}]


def test_coerce_gams_tool_arguments_supports_positional_lists():
    result = chat_service._coerce_gams_tool_arguments(
        "get_info_by_eids",
        [["RKD-1"], ["EID", "IME"]],
    )

    assert result == {"eids": ["RKD-1"], "columns": ["EID", "IME"]}


def test_parse_gams_json_response_raises_chat_service_error_for_empty_payload():
    with pytest.raises(chat_service.ChatServiceError) as exc_info:
        chat_service._parse_gams_json_response("```json\n```")

    assert exc_info.value.status_code == 502
    assert "neveljaven prazen JSON odgovor" in str(exc_info.value)


def test_parse_gams_json_response_raises_chat_service_error_for_invalid_json():
    with pytest.raises(chat_service.ChatServiceError) as exc_info:
        chat_service._parse_gams_json_response("to ni json")

    assert exc_info.value.status_code == 502
    assert "neveljaven" in str(exc_info.value)


def test_parse_gams_json_response_raises_chat_service_error_for_plain_text():
    with pytest.raises(chat_service.ChatServiceError) as exc_info:
        chat_service._parse_gams_json_response("Rižana - Vrtec je enota v občini Koper.")

    assert exc_info.value.status_code == 502
    assert "neveljaven" in str(exc_info.value)


def test_build_gams_tool_result_message_matches_prompt_contract():
    message = chat_service._build_gams_tool_result_message(
        "get_info_by_eids",
        [{"EID": "RKD-1", "IME": "Prvi spomenik"}],
    )

    parsed = chat_service.json.loads(message)
    assert parsed["function_call"] == "get_info_by_eids"
    assert parsed["function_return"] == [{"EID": "RKD-1", "IME": "Prvi spomenik"}]


def test_build_gams_tool_result_message_adds_hint_for_endangered_tools():
    message = chat_service._build_gams_tool_result_message(
        "top_k_endangered_in_region",
        ["RKD-1", "RKD-2"],
    )

    parsed = chat_service.json.loads(message)
    assert "hint" in parsed
    assert "get_info_by_eids" in parsed["hint"]

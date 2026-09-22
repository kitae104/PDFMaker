"""LessonChapter/LessonContent 입력 정규화(W2) 테스트."""

import pytest

from app.schemas.pipeline import LessonChapter, LessonContent


def chapter(**overrides) -> LessonChapter:
    return LessonChapter.model_validate({"title": "1. 제목", "explanation": "설명", **overrides})


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ([{"term": "안료", "definition": "색을 내는 가루"}], [{"term": "안료", "definition": "색을 내는 가루"}]),
        ([{"name": "안료", "description": "색을 내는 가루"}], [{"term": "안료", "definition": "색을 내는 가루"}]),
        ([{"용어": "안료", "설명": "색을 내는 가루"}], [{"term": "안료", "definition": "색을 내는 가루"}]),
        ([{"keyword": "안료", "meaning": "가루"}, {"word": "수지", "explanation": "접착"}], [{"term": "안료", "definition": "가루"}, {"term": "수지", "definition": "접착"}]),
        ([{"Term": "안료", "Desc": "가루"}], [{"term": "안료", "definition": "가루"}]),
        ([{"term": "안료", "definition": None}], [{"term": "안료", "definition": ""}]),
        ([{"term": "안료"}], [{"term": "안료", "definition": ""}]),
        ([{"term": 3, "definition": ["a", "b"]}], [{"term": "3", "definition": "a, b"}]),
        (["안료: 색을 내는 가루", "수지"], [{"term": "안료", "definition": "색을 내는 가루"}, {"term": "수지", "definition": ""}]),
        ([["안료", "가루"]], [{"term": "안료", "definition": "가루"}]),
        ([{"안료": "가루", "수지": "접착"}], [{"term": "안료", "definition": "가루"}, {"term": "수지", "definition": "접착"}]),
        # W5: 정의만 있는 행은 편집기 입력 유실을 막기 위해 보존한다. term·definition이 모두 빈 항목만 제거.
        ([None, {"term": "", "definition": "빈 용어"}, {"term": None}, "  "], [{"term": "", "definition": "빈 용어"}]),
        ([{"term": "", "definition": ""}, {"term": "  ", "definition": None}], []),
        (None, []),
        ({"term": "안료", "definition": "가루"}, [{"term": "안료", "definition": "가루"}]),
    ],
)
def test_terms_are_normalized_to_term_definition(raw, expected):
    assert chapter(terms=raw).terms == expected


def test_normalized_terms_have_exactly_two_keys():
    result = chapter(terms=[{"name": "안료", "description": "가루", "extra": "무시"}])
    assert result.terms == [{"term": "안료", "definition": "가루"}]


def test_optional_chapter_fields_default_instead_of_failing():
    result = chapter()
    assert result.learning_objectives == []
    assert result.key_points == []
    assert result.terms == []
    assert result.beginner_explanation == ""
    assert result.summary == ""
    assert result.timestamp == ""


def test_none_values_and_list_items_are_cleaned():
    result = chapter(
        beginner_explanation=None,
        summary=None,
        timestamp=None,
        key_points=["핵심", None, 3, ""],
        learning_objectives="하나의 목표",
    )
    assert result.beginner_explanation == ""
    assert result.key_points == ["핵심", "3"]
    assert result.learning_objectives == ["하나의 목표"]


def test_required_fields_still_required():
    with pytest.raises(ValueError):
        LessonChapter.model_validate({"title": "제목"})


def test_serialized_shape_is_unchanged():
    content = LessonContent.model_validate(
        {
            "title": "문서",
            "overview": "개요",
            "learning_objectives": ["목표", None],
            "chapters": [{"title": "1. 제목", "explanation": "설명", "terms": [{"용어": "안료", "정의": "가루"}]}],
            "final_summary": ["정리"],
            "review_questions": ["질문"],
        }
    )
    dumped = content.model_dump()
    assert set(dumped) == {"title", "overview", "learning_objectives", "chapters", "final_summary", "review_questions"}
    assert set(dumped["chapters"][0]) == {
        "title",
        "learning_objectives",
        "explanation",
        "beginner_explanation",
        "key_points",
        "terms",
        "timestamp",
        "summary",
    }
    assert dumped["learning_objectives"] == ["목표"]
    assert dumped["chapters"][0]["terms"] == [{"term": "안료", "definition": "가루"}]
    # 저장된 JSON 재로딩(get_document_draft 경로)도 그대로 통과해야 한다.
    assert LessonContent.model_validate_json(content.model_dump_json()) == content

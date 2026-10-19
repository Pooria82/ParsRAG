"""Questions that ask several things are searched part by part."""

from unittest.mock import MagicMock

import pytest

from backend.core.domain.documents import ExtractedNode
from backend.core.service.question_parts import question_parts
from backend.core.strategies.multi_doc_utils import (
    retrieve_question_parts,
    with_part_evidence,
)


@pytest.mark.parametrize(
    ("question", "parts"),
    [
        (
            "پنل Continue با چه کلید ترکیبی به مود Edit می‌رود و در مثال چه فیلدهایی به مدل کاربر اضافه شد؟",
            [
                "پنل Continue با چه کلید ترکیبی به مود Edit می‌رود",
                "در مثال چه فیلدهایی به مدل کاربر اضافه شد؟",
            ],
        ),
        (
            "What is the budget, and how long does phase two take?",
            ["What is the budget", "how long does phase two take?"],
        ),
        (
            "تصمیم نهایی پروژه چه بود؟ برای تست واحد و تست سیستم چه رویکردی توصیه شد؟",
            [
                "تصمیم نهایی پروژه چه بود؟",
                "برای تست واحد و تست سیستم چه رویکردی توصیه شد؟",
            ],
        ),
    ],
)
def test_questions_with_several_asks_are_split(question: str, parts: list[str]) -> None:
    assert question_parts(question) == parts


@pytest.mark.parametrize(
    "question",
    [
        "تست واحد و تست سیستم چیست؟",
        "هزینه و زمان فاز دوم چقدر است؟",
        "راهنمای کدام ابزار در فصل اول و دوم آمده است؟",
        "Explain the cost and the schedule.",
        "چهار ابزار و پنج روش را نام ببر",
    ],
)
def test_a_single_question_is_not_split(question: str) -> None:
    assert question_parts(question) == [question]


def test_a_clause_without_its_own_question_stays_with_the_one_before() -> None:
    question = "کدام دو ابزار در فصل اول و دوم آمده و ابزار مانکی همان کدام ابزار است؟"
    assert question_parts(question) == [
        "کدام دو ابزار در فصل اول و دوم آمده",
        "ابزار مانکی همان کدام ابزار است؟",
    ]


def _node(text: str, score: float) -> ExtractedNode:
    return ExtractedNode(text=text, metadata={"filename": "a.docx"}, score=score)


def test_each_part_is_searched_on_its_own() -> None:
    repo = MagicMock()
    repo.similarity_search.side_effect = lambda query, **kwargs: [_node(query, 0.8)]

    found = retrieve_question_parts(
        repo, "کلید چه بود و فیلدها کدام بودند؟", ["a.docx"], None, "s", 4
    )

    assert [[node.text for node in part] for part in found] == [
        ["کلید چه بود"],
        ["فیلدها کدام بودند؟"],
    ]
    assert retrieve_question_parts(repo, "کلید چه بود؟", ["a.docx"], None, "s", 4) == []


def test_each_part_keeps_its_best_excerpts() -> None:
    kept = [_node("answer to part one", 0.9)]
    parts = [
        [_node("answer to part one", 0.9)],
        [
            _node("answer to part two", 0.62),
            _node("second hit", 0.61),
            _node("third", 0.6),
        ],
        [_node("too weak", 0.3)],
    ]

    result = with_part_evidence(kept, parts, per_part=2, minimum_score=0.55)

    assert [node.text for node in result] == [
        "answer to part one",
        "answer to part two",
        "second hit",
    ]


def test_long_runs_of_spaces_are_split_quickly() -> None:
    import time

    started = time.perf_counter()
    question_parts("چه " + " " * 20000 + "x")
    question_parts("چه کسی آمد" + " ،" * 10000 + " و چه گفت؟")

    assert time.perf_counter() - started < 1.0


def test_comma_before_and_still_splits() -> None:
    assert question_parts("چه کسی پروژه را تأیید کرد، و چه تاریخی ثبت شد؟") == [
        "چه کسی پروژه را تأیید کرد",
        "چه تاریخی ثبت شد؟",
    ]

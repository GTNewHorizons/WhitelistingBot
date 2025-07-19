from enum import Enum
from typing import Any, Callable, List, Optional


class QuestionType(str, Enum):
    INTEGER = "integer"
    BOOL = "boolean"
    FREE = "free"


class Question:
    def __init__(
        self, name: str, text: str, question_type: QuestionType, checks: Optional[List[Callable[[Any], bool]]], on_check_error: Optional[Callable[[Any], Any]]
    ):
        self.name: str = name
        self.text: str = text
        self.question_type: QuestionType = question_type
        self.checks: Optional[List[Callable[[Any], bool]]] = checks
        self.on_check_error: Optional[Callable[[Any], Any]] = on_check_error

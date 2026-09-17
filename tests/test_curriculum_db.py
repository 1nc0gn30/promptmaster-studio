"""Tests for CurriculumDB and educational lessons in promptmaster_studio.engine.curriculum_db."""

import pytest

from promptmaster_studio.engine.curriculum_db import (
    LESSONS_CATALOG,
    TEMPLATES_CATALOG,
    get_all_tags,
    get_categories,
    get_lesson,
    get_template,
    list_lessons,
    list_templates,
    search_curriculum,
)
from promptmaster_studio.models import CurriculumLesson, LessonDifficulty, PromptTemplate


class TestCurriculumDB:
    """Test curriculum catalog querying, filtering, search, and data integrity."""

    def test_curriculum_catalog_not_empty(self):
        assert len(LESSONS_CATALOG) >= 5
        for lesson in LESSONS_CATALOG:
            assert isinstance(lesson, CurriculumLesson)
            assert lesson.id
            assert lesson.title
            assert lesson.summary
            assert lesson.content_markdown
            assert lesson.estimated_minutes > 0
            assert len(lesson.key_takeaways) >= 1

    def test_templates_catalog_not_empty(self):
        assert len(TEMPLATES_CATALOG) >= 10
        for tmpl in TEMPLATES_CATALOG:
            assert isinstance(tmpl, PromptTemplate)
            assert tmpl.id
            assert tmpl.title
            assert tmpl.template_str

    def test_get_lesson_by_id(self):
        lesson = get_lesson("lesson-01-core-anatomy")
        assert lesson is not None
        assert "Anatomy" in lesson.title

        # Test non-existent ID
        missing = get_lesson("non_existent_lesson_999")
        assert missing is None

    def test_get_template_by_id(self):
        tmpl = get_template("code-refactoring-clean")
        assert tmpl is not None
        assert "Refactoring" in tmpl.title or "code" in tmpl.id

        missing = get_template("non_existent_template_999")
        assert missing is None

    def test_list_lessons_filtering(self):
        foundations = list_lessons(category="foundations")
        assert len(foundations) >= 1
        assert all(l.category == "foundations" for l in foundations)

        beginner = list_lessons(difficulty="beginner")
        assert len(beginner) >= 1
        assert all(l.difficulty == LessonDifficulty.BEGINNER.value for l in beginner)

    def test_list_templates_filtering(self):
        coding_templates = list_templates(category="coding")
        assert len(coding_templates) >= 1
        assert all(t.category == "coding" for t in coding_templates)

    def test_search_curriculum(self):
        results = search_curriculum("xml")
        assert results["lessons_count"] > 0 or results["templates_count"] > 0
        assert "lessons" in results
        assert "templates" in results

    def test_get_categories_and_tags(self):
        cats = get_categories()
        assert "lesson_categories" in cats
        assert "template_categories" in cats
        assert len(cats["lesson_categories"]) >= 3

        tags = get_all_tags()
        assert len(tags) >= 5
        assert isinstance(tags, list)

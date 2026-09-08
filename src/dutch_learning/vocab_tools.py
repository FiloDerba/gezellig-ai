"""Tools that let the assistant look into the learner's own vocabulary.

Registered on the ai-playground agent, so answers can be grounded in the words this
learner has actually met rather than Dutch in general. The docstrings are what the model
sees when deciding whether to call them, so they are written for the model.
"""

from dutch_learning import data

SEARCH_LIMIT = 40
SUMMARY_SAMPLE = 30


def _line(word) -> str:
    parts = [f"{word.dutch} = {word.english}"]
    tags = ", ".join(part for part in (word.word_type, word.chapter) if part)
    if tags:
        parts.append(f"({tags})")
    parts.append(f"seen {word.times_reviewed}x")
    if word.last_seen:
        parts.append(f"last {word.last_seen.isoformat()}")
    parts.append(word.srs.maturity)
    return " · ".join(parts)


def search_my_vocabulary(query: str = "", limit: int = SEARCH_LIMIT) -> str:
    """Search the Dutch words this learner has already studied and been tested on.

    Use this whenever the answer should refer to words the learner actually knows — for
    example when writing example sentences, quizzing them, or being asked "which words do
    I know". Pass a Dutch or English substring as `query` to narrow it, or leave it empty
    to get the most recently studied words. Returns one line per word with how often it
    was reviewed, when it was last seen, and whether it is new, learning or mature.
    """
    limit = max(1, min(limit, 200))
    words = data.encountered(search=query.strip() or None, limit=limit)
    if not words:
        if query.strip():
            return f"No studied word matches {query!r}. The learner may not have met it yet."
        return "The learner has not reviewed any words yet."
    return "\n".join(_line(word) for word in words)


def my_vocabulary_summary() -> str:
    """How much Dutch this learner has covered so far.

    Use this for questions about their overall progress, or to orient yourself before
    giving advice about what to study next.
    """
    stats = data.overview()
    studied = data.encountered(limit=SUMMARY_SAMPLE)
    lines = [
        f"The learner has reviewed {len(data.encountered())} distinct words "
        f"out of {stats.total_words} in their deck.",
        f"{stats.learning} are in learning, {stats.mature} are mature, "
        f"{stats.due_today} are due today.",
        f"Study streak: {stats.streak} day(s). Reviews all time: {stats.total_reviews}.",
    ]
    if studied:
        chapters = sorted({word.chapter for word in studied if word.chapter})
        lines.append(f"Chapters touched so far: {', '.join(chapters) or 'none recorded'}.")
        lines.append("Most recently studied:\n" + "\n".join(_line(word) for word in studied))
    return "\n".join(lines)


TOOLS = [search_my_vocabulary, my_vocabulary_summary]

CONTEXT = """
You are also this person's Dutch tutor. They keep a spaced-repetition deck, and you can
read it with the search_my_vocabulary and my_vocabulary_summary tools.

Call search_my_vocabulary before writing Dutch example sentences or quizzing them, and
build on words they have already met wherever you can. If you must introduce a new word,
say so. Call my_vocabulary_summary when asked about progress or what to learn next.
Never claim to know their vocabulary without calling a tool first.
"""

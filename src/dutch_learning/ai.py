from pydantic_ai import Agent

SYSTEM_PROMPT = (
    "You are a Dutch language tutor. Answer concisely in English. "
    "Give hints, etymology, mnemonics, or example sentences as requested. "
    "Do not directly give away the translation if the user is still trying to recall it."
)


def make_hint_agent(model: str = "google-gla:gemini-2.0-flash") -> Agent:
    return Agent(model, system_prompt=SYSTEM_PROMPT)


def get_hint(agent: Agent, dutch: str, word_type: str, english: str, question: str) -> str:
    prompt = (
        f"The user is studying the Dutch word '{dutch}' ({word_type}, meaning '{english}'). "
        f"Their question: {question}"
    )
    result = agent.run_sync(prompt)
    return result.output

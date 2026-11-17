from dotenv import load_dotenv

from ai_playground.agent import Agent, token_usage

load_dotenv()


def main() -> None:
    agent = Agent()

    while True:
        query = input("You: ")
        if query.lower() in ("exit", "quit"):
            break

        before = len(agent.messages)
        print(f"Assistant: {agent.chat(query)}")
        print(
            f"  [tokens: {token_usage(agent.messages[before:])}; conversation: "
            f"{token_usage(agent.messages)}]"
        )


if __name__ == "__main__":
    main()

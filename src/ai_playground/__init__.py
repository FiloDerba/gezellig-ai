from dotenv import load_dotenv

from ai_playground.agent import Agent

load_dotenv()


def main() -> None:
    agent = Agent()

    while True:
        query = input("You: ")
        if query.lower() in ("exit", "quit"):
            break

        response = agent.chat(query)
        print(f"Assistant: {response}")


if __name__ == "__main__":
    main()

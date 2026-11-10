import argparse

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    from rag_playground import rag
    from rag_playground.index import load_index

    parser = argparse.ArgumentParser(description="Ask questions about the D&D campaign.")
    parser.add_argument("--agentic", action="store_true", help="let the model decide to search")
    args = parser.parse_args()

    index = load_index()
    agent = rag.agentic(index) if args.agentic else None

    mode = "Agentic" if args.agentic else "Two-step"
    print(f"{mode} RAG over {len(index.chunks)} chunks ({index.store}).")
    while True:
        query = input("You: ")
        if query.lower() in ("exit", "quit"):
            break
        print(f"Assistant: {agent.chat(query) if agent else rag.two_step(index, query)}")


if __name__ == "__main__":
    main()

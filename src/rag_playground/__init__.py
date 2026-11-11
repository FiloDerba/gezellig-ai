import argparse

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    from rag_playground import rag
    from rag_playground.index import load_index

    parser = argparse.ArgumentParser(description="Ask questions about the D&D campaign.")
    parser.add_argument("--agentic", action="store_true", help="let the model decide to search")
    parser.add_argument("--hybrid", action="store_true", help="search by keyword as well as vector")
    args = parser.parse_args()

    index = load_index(hybrid=args.hybrid)
    agent = rag.agentic(index) if args.agentic else None

    mode = "Agentic" if args.agentic else "Two-step"
    search = "hybrid" if args.hybrid else "vector"
    print(f"{mode} RAG over {len(index.chunks)} chunks ({index.store}, {search} search).")
    while True:
        query = input("You: ")
        if query.lower() in ("exit", "quit"):
            break
        print(f"Assistant: {agent.chat(query) if agent else rag.two_step(index, query)}")


if __name__ == "__main__":
    main()

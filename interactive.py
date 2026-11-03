from src.agent import create_ai_agent, run_queries


def main():
    agent = create_ai_agent()

    while True:
        user_input = input("Zadaj pytanie: ")
        if user_input.lower() in ["exit", "quit"] or user_input.strip() == "":
            break

        try:
            run_queries(agent, [user_input])
            print("\n" * 3)
        except Exception as e:
            print(f"Wystąpił błąd podczas przetwarzania zapytania: {e}\n")


if __name__ == "__main__":
    main()

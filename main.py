from src.database import (
    get_table_counts,
    get_total_records,
    get_top_expensive_products,
    get_customers_count_by_city,
)
from src.agent import create_ai_agent, run_queries


def main():
    try:
        counts = get_table_counts()
        print("--- Liczba rekordów w każdej tabeli ---")
        for table, count in counts.items():
            print(f"{table:<25} : {count}")
        print()

        total_records = sum(counts.values())
        print(f"Liczba rekordów we wszystkich tabelach: {total_records}\n")

        expensive_products = get_top_expensive_products()
        print("--- 5 najdroższych produktów ---")
        for name, price in expensive_products:
            print(f"• {name:<25} : {price}")
        print()

        customers_in_london = get_customers_count_by_city("London")
        print(f"Liczba klientów z siedzibą w Londynie: {customers_in_london}\n")

    except Exception as e:
        print(f"Connection error: {e}")

    agent = create_ai_agent()

    example_queries = [
        "Ile mamy rekordów w bazie we wszystkich tabelach na raz?",
        "Wypisz nazwy i ceny 5 najdroższych produktów.",
        "Ilu klientów ma swoją siedzibę w Londynie?",
    ]

    run_queries(agent, example_queries)


if __name__ == "__main__":
    main()

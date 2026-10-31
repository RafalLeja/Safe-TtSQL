## Getting started

### To initialize the database in Postgres, run this command

```bash
createdb -U postgres northwind
psql -U postgres -d northwind -f northwind.sql
psql -U postgres -d northwind
```

### Credentials

Create a `.env` file in the root directory with the following content:

```bash
DB_USER=postgres
DB_PASSWORD=your_password
OPENAI_API_KEY=your_openai_api_key
```

## Models to test

1. gpt-6-luna vs gpt-5.2
2. or-gpt-oss-120b vs or-gpt-oss-20b

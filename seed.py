from main import execute, query

if query("SELECT id FROM categories"):
    print("База не пустая, сиды не нужны")
else:
    food = execute("INSERT INTO categories (name, monthly_limit) VALUES (?, ?)", ("Продукты", 20000))
    taxi = execute("INSERT INTO categories (name, monthly_limit) VALUES (?, ?)", ("Транспорт", 5000))
    execute("INSERT INTO expenses (category_id, amount, date, comment) VALUES (?, ?, ?, ?)", (food, 1500, "2026-10-03", "хлеб, молоко"))
    execute("INSERT INTO expenses (category_id, amount, date, comment) VALUES (?, ?, ?, ?)", (taxi, 400, "2026-10-05", "такси"))
    print("Тестовые данные добавлены")
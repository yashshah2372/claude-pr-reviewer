"""Small user service used to demo the reviewer."""
import sqlite3


def find_users(conn: sqlite3.Connection, name: str) -> list[tuple]:
    cur = conn.cursor()
    cur.execute(f"SELECT id, name, email FROM users WHERE name LIKE '%{name}%'")
    return cur.fetchall()


def page(items: list, page_num: int, size: int = 20) -> list:
    start = page_num * size
    return items[start:start + size + 1]


def average_age(users: list[dict]) -> float:
    return sum(u["age"] for u in users) / len(users)

from reviewer import diff
from reviewer.review import Comment, Review, to_github_review

SAMPLE = """diff --git a/app/db.py b/app/db.py
index 1111111..2222222 100644
--- a/app/db.py
+++ b/app/db.py
@@ -10,4 +10,5 @@ def get_user(conn, user_id):
     cur = conn.cursor()
-    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
+    cur.execute(f"SELECT * FROM users WHERE id = {user_id}")
+    row = cur.fetchone()
     return cur.fetchone()
diff --git a/old.txt b/old.txt
deleted file mode 100644
--- a/old.txt
+++ /dev/null
@@ -1 +0,0 @@
-bye
diff --git a/package-lock.json b/package-lock.json
--- a/package-lock.json
+++ b/package-lock.json
@@ -1 +1 @@
-{}
+{"lockfileVersion": 3}
"""


def test_parse_tracks_new_line_numbers():
    files = diff.parse(SAMPLE)
    assert [f.path for f in files] == ["app/db.py", "package-lock.json"]
    db = files[0]
    assert db.commentable == {10, 11, 12, 13}
    assert "   11 +    cur.execute(f\"SELECT" in db.text


def test_select_reports_what_it_skips():
    files = diff.parse(SAMPLE)
    kept, skipped = diff.select(files, max_chars=10_000, skip_globs=("*.json",))
    assert [f.path for f in kept] == ["app/db.py"]
    assert skipped == ["package-lock.json (ignored pattern)"]

    kept, skipped = diff.select(files, max_chars=10, skip_globs=())
    assert kept == [] and len(skipped) == 2


def test_comments_off_the_diff_move_to_summary():
    files = diff.parse(SAMPLE)
    review = Review(
        summary="Switches the query to an f-string.",
        verdict="request_changes",
        comments=[
            Comment(path="app/db.py", line=11, severity="security", body="SQL injection; keep the parameterised query."),
            Comment(path="app/db.py", line=99, severity="bug", body="Not in the diff."),
        ],
    )
    out = to_github_review(review, files, skipped=["big.py (diff too large for one review)"])
    assert out["event"] == "REQUEST_CHANGES"
    assert out["comments"] == [
        {"path": "app/db.py", "line": 11, "side": "RIGHT", "body": "**security**: SQL injection; keep the parameterised query."}
    ]
    assert "`app/db.py:99`" in out["body"] and "big.py" in out["body"]

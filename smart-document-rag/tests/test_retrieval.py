import json
import unittest
from pathlib import Path

from rag import make_chunks, retrieve


FIXTURES = Path(__file__).with_name("retrieval_cases.json")


class RetrievalTest(unittest.TestCase):
    def test_vietnamese_corpus(self):
        data = json.loads(FIXTURES.read_text(encoding="utf-8"))
        self.assertEqual(len(data["documents"]), 10)
        self.assertEqual(len(data["questions"]), 15)
        chunks = [
            {**chunk, "filename": document["filename"]}
            for document in data["documents"]
            for chunk in make_chunks(document["content"])
        ]
        for case in data["questions"]:
            with self.subTest(question=case["question"]):
                matches = retrieve(case["question"], chunks)
                self.assertLessEqual(len(matches), 3)
                if case["expected"] is None:
                    self.assertEqual(matches, [])
                else:
                    self.assertTrue(matches)
                    self.assertEqual(matches[0]["filename"], case["expected"])
                    self.assertIn(matches[0], chunks)

    def test_page_and_literal_text(self):
        chunks = list(make_chunks("", ["", "Tài liệu\ntrang hai"]))
        self.assertEqual(chunks, [
            {"page_number": 2, "chunk_index": 1, "content": "Tài liệu\ntrang hai"}
        ])

    def test_maximum_three_results(self):
        chunks = [{"content": "thư viện", "chunk_index": i} for i in range(10)]
        self.assertEqual(len(retrieve("THƯ VIỆN", chunks)), 3)

    def test_long_text_chunks_are_bounded(self):
        chunks = list(make_chunks("x" * 2500))
        self.assertTrue(all(0 < len(chunk["content"]) <= 900 for chunk in chunks))

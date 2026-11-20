import re
from heapq import nlargest

from sklearn.feature_extraction.text import TfidfVectorizer, strip_accents_unicode
from sklearn.metrics.pairwise import cosine_similarity


QUESTION_LIMIT = 500
MIN_SIMILARITY = 0.18
STOP_WORDS = [
    "bao", "cach", "cho", "co", "cua", "duoc", "gi", "hay", "khong", "khi",
    "la", "nao", "nhieu", "nhu", "o", "se", "the", "thi", "toi", "va", "ve",
]


def normalize_vietnamese(text):
    return strip_accents_unicode(text.casefold().replace("đ", "d"))


def split_document(content):
    # Keep the stored wording and internal line breaks.
    text = content.strip()
    size, overlap = 900, 120
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundaries = list(re.finditer(r"\s+", text[start + size // 2:end]))
            if boundaries:
                end = start + size // 2 + boundaries[-1].start()
        yield text[start:end].strip()
        if end == len(text):
            break
        start = end - overlap
        boundary = re.search(r"\s+", text[start:end])
        if boundary:
            start += boundary.end()


def make_chunks(content, pages=None):
    sections = enumerate(pages, start=1) if pages is not None else [(None, content)]
    index = 0
    for page_number, text in sections:
        for passage in split_document(text):
            if passage:
                index += 1
                yield {"chunk_index": index, "page_number": page_number, "content": passage}


def retrieve(question, chunks, *, ngram_range=(1, 2)):
    if not chunks:
        return []
    # Vietnamese spaces separate syllables. Adjacent pairs help preserve compounds.
    vectorizer = TfidfVectorizer(
        preprocessor=normalize_vietnamese,
        ngram_range=ngram_range,
        token_pattern=r"(?u)\b\w+\b",
        stop_words=STOP_WORDS,
    )
    analyze = vectorizer.build_analyzer()
    if not analyze(question):
        return []
    try:
        vectors = vectorizer.fit_transform(chunk["content"] for chunk in chunks)
    except ValueError as error:
        if "empty vocabulary" not in str(error):
            raise
        return []
    scores = cosine_similarity(vectorizer.transform([question]), vectors)[0]
    ranked = nlargest(3, range(len(chunks)), key=scores.__getitem__)
    return [chunks[index] for index in ranked if scores[index] >= MIN_SIMILARITY]

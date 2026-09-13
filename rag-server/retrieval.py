from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

HIGH_THRESHOLD = 0.5
MEDIUM_THRESHOLD = 0.2


def search(documents, query):
    if not documents:
        return {"citations": [], "confidence": "insufficient"}

    texts = [doc["text"] for doc in documents]
    vectorizer = TfidfVectorizer()
    doc_vectors = vectorizer.fit_transform(texts)
    query_vector = vectorizer.transform([query])

    similarities = cosine_similarity(query_vector, doc_vectors)[0]

    best_idx = similarities.argmax()
    best_score = similarities[best_idx]

    if best_score >= MEDIUM_THRESHOLD:
        confidence = "high" if best_score >= HIGH_THRESHOLD else "medium"
        citations = [{
            "source": documents[best_idx]["source"],
            "excerpt": documents[best_idx]["text"][:200],
        }]
        return {"citations": citations, "confidence": confidence, "score": float(best_score)}

    return {"citations": [], "confidence": "insufficient"}
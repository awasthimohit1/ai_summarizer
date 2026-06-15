import chromadb
from sentence_transformers import SentenceTransformer
import json

# Initialize the exact same vector environment
chroma_client = chromadb.PersistentClient(path="./vector_db")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
vector_collection = chroma_client.get_collection(name="engineering_blogs")

def semantic_search(user_query, max_results=3):
    # Turn the user's plain English search question into a vector coordinate
    query_vector = embedding_model.encode(user_query).tolist()
    
    # Query ChromaDB for the mathematically closest vectors
    results = vector_collection.query(
        query_embeddings=[query_vector],
        n_results=max_results
    )
    
    print(f"\n🔍 Semantic Search Results for: '{user_query}'\n" + "="*50)
    
    if not results['documents'][0]:
        print("No matching articles found in the vector database.")
        return

    for i in range(len(results['documents'][0])):
        doc = results['documents'][0][i]
        meta = results['metadatas'][0][i]
        
        print(f"\n📈 Result #{i+1}")
        print(f"Title: {meta['title']}")
        print(f"Url: {meta['link']}")
        print(f"Match Context: {doc}\n")

if __name__ == "__main__":
    # Test queries you can try once your DB is populated:
    # "show me articles discussing agent frameworks or distributed systems"
    # "scaling large language models or cluster topology"
    query = input("Enter what you are looking for: ")
    semantic_search(query)
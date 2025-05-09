import os
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from typing import List, Dict
from flask import Flask, request, jsonify
from flask_cors import CORS


# Load environment variables from .env file
load_dotenv()
app = Flask(__name__)
CORS(app)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class Book(BaseModel):
    title: str
    author: List[str]
    price: float
    summary: str
    purchase_links: Dict[str, str]  # Store multiple purchase links as a dictionary

class Output(BaseModel):
    books: List[Book]

def analyze_query(query: str) -> bool:
    """Check if the query is related to books or bookshops."""
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": (
                    "Please analyze the user's message and determine if it is related to books "
                    "or bookshops. Return 'true' if it is related, and 'false' if it is not."
                ),
            },
            {"role": "user", "content": query},
        ],
    )
    answer = response.choices[0].message.content.strip().lower()
    return answer == "true"

def generate_response(query: str) -> Output:
    """Generate a helpful response including purchase links."""
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system", 
                "content": """Your role is to recommend 3 books based on the user's query. 
                For each book, provide:
                - title: The book's title
                - author: List of authors
                - price: A reasonable price in euros
                - summary: A brief summary of the book
                - purchase_links: A dictionary with two keys:
                  * amazon: The Amazon purchase link
                  * lafeltrinelli: The LaFeltrinelli purchase link
                
                Format the response as a JSON object with a 'books' array containing these fields.
                Make sure to provide both Amazon and LaFeltrinelli links for each book."""
            },
            {"role": "user", "content": query},
        ],
    )
    
    # Parse the response and convert it to our Output model
    try:
        import json
        content = response.choices[0].message.content
        data = json.loads(content)
        return Output(**data)
    except Exception as e:
        print(f"Error parsing response: {e}")
        return Output(books=[])

@app.route('/chatbot', methods=['POST'])
def chatbot():
    try:
        data = request.get_json()
        query = data.get('query')
        print(query)

        if not query:
            return jsonify({"error": "No query provided"}), 400

        is_book_related = analyze_query(query)
        print(f"Is book related? {is_book_related}")

        if not is_book_related:
            return jsonify({
                "response": "I'm just a bookseller, I can help you find the next book to read but nothing else",
                "books": None
            })
        else:
            response_text = "Here are some books you might like:\n\n"
            answer = generate_response(query)
            
            # Format the response text to include both purchase links
            for i, book in enumerate(answer.books, 1):
                response_text += f"\nBook {i}:\n"
                response_text += f"📖 {book.title}\n"
                response_text += f"👤 {', '.join(book.author)}\n"
                response_text += f"💰 €{book.price:.2f}\n"
                response_text += f"📚 {book.summary}\n"
                response_text += "Purchase Links:\n"
                response_text += f"🛒 Amazon: {book.purchase_links['amazon']}\n"
                response_text += f"📚 LaFeltrinelli: {book.purchase_links['lafeltrinelli']}\n"
            
            return jsonify({
                "response": response_text,
                "books": [book.dict() for book in answer.books]
            })
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)

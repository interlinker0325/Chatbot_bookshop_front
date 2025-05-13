import os
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from typing import List, Dict, Optional
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime


# Load environment variables from .env file
load_dotenv()
app = Flask(__name__)
CORS(app)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Store chat histories (in a real application, you'd want to use a database)
chat_histories = {}

class Message(BaseModel):
    role: str
    content: str
    timestamp: datetime = datetime.now()

class ChatHistory(BaseModel):
    messages: List[Message] = []
    last_recommended_books: List[Dict] = []  # Store the last set of recommended books
    last_query: Optional[str] = None  # Store the last query for context

class Book(BaseModel):
    title: str
    author: List[str]
    price: float
    summary: str
    purchase_links: Dict[str, str]

class Output(BaseModel):
    books: List[Book]

def analyze_query(query: str, chat_history: List[Message]) -> bool:
    """Check if the query is related to books or bookshops."""
    messages = [
        {
            "role": "system",
            "content": (
                "Please analyze the user's message and determine if it is related to books "
                "or bookshops. Return 'true' if it is related, and 'false' if it is not."
            ),
        }
    ]
    
    # Add relevant chat history context
    for msg in chat_history[-3:]:  # Only use last 3 messages for context
        messages.append({"role": msg.role, "content": msg.content})
    
    messages.append({"role": "user", "content": query})
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages
    )
    answer = response.choices[0].message.content.strip().lower()
    return answer == "true"

def is_book_followup(query: str, last_books: List[Dict]) -> Optional[Dict]:
    """Check if the query is about a specific book from the last recommendation."""
    if not last_books:
        return None

    messages = [
        {
            "role": "system",
            "content": """Analyze if the user's question is about one of the previously recommended books.
            If yes, return the book's details in JSON format. If no, return 'null'.
            
            Example response for a match:
            {
                "title": "Book Title",
                "author": ["Author Name"],
                "price": 19.99,
                "summary": "Book summary",
                "purchase_links": {
                    "amazon": "https://amazon.com/book",
                    "lafeltrinelli": "https://lafeltrinelli.it/book"
                }
            }
            
            Example response for no match:
            null"""
        },
        {
            "role": "user",
            "content": f"Previous books: {last_books}\n\nUser question: {query}"
        }
    ]
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages
    )
    
    try:
        content = response.choices[0].message.content.strip()
        if content.lower() == 'null':
            return None
        import json
        return json.loads(content)
    except:
        return None

def is_criteria_followup(query: str, last_query: str) -> bool:
    """Check if the query is a follow-up request with specific criteria."""
    messages = [
        {
            "role": "system",
            "content": """Analyze if the user's message is a follow-up request with specific criteria (like language, publisher, etc.).
            Return 'true' if it is a follow-up with criteria, 'false' if it is not.
            
            Examples of follow-up criteria:
            - "anything in Italian?"
            - "from Mondadori publishing house?"
            - "books in Spanish?"
            - "anything from Penguin?"
            
            Examples of non-follow-up:
            - "tell me more about this book"
            - "what's the price?"
            - "who is the author?"
            """
        },
        {
            "role": "user",
            "content": f"Previous query: {last_query}\n\nCurrent query: {query}"
        }
    ]
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages
    )
    answer = response.choices[0].message.content.strip().lower()
    return answer == "true"

def get_book_details(book: Dict, query: str) -> str:
    """Get detailed information about a specific book based on the user's query."""
    messages = [
        {
            "role": "system",
            "content": f"""You are a knowledgeable bookseller. Provide detailed information about this book:
            Title: {book['title']}
            Author: {', '.join(book['author'])}
            Summary: {book['summary']}
            
            The user asked: {query}
            
            Provide a detailed, informative response that directly addresses the user's question about this specific book.
            Include relevant details about the book's themes, writing style, reception, and why it might interest the reader.
            Keep the response concise but informative."""
        }
    ]
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages
    )
    
    return response.choices[0].message.content.strip()

def fetch_real_links(title: str, author: str) -> dict:
    """Ask GPT to provide real Amazon.it and lafeltrinelli.it links for a book."""
    prompt = (
        f"How can I find the book '{title}' by {author}? "
        "Please give me only the direct Amazon.it and lafeltrinelli.it links in JSON format as: "
        '{"amazon": "...", "lafeltrinelli": "..."}'
    )
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=200
    )
    import json
    try:
        content = response.choices[0].message.content.strip()
        # Try to extract JSON from the response
        start = content.find('{')
        end = content.rfind('}') + 1
        if start != -1 and end != -1:
            content = content[start:end]
        links = json.loads(content)
        if not (isinstance(links, dict) and 'amazon' in links and 'lafeltrinelli' in links):
            raise ValueError('Missing links')
        return links
    except Exception as e:
        print(f"Error fetching real links for {title}: {e}")
        # Fallback: return search links
        title_url = title.lower().replace(' ', '+')
        return {
            "amazon": f"https://www.amazon.it/s?k={title_url}",
            "lafeltrinelli": f"https://www.lafeltrinelli.it/search?q={title_url}"
        }

def generate_response(query: str, chat_history: List[Message], criteria: Optional[str] = None) -> Output:
    """Generate a helpful response including purchase links."""
    messages = [
        {
            "role": "system", 
            "content": f"""You are a book recommendation assistant. Based on the user's query and conversation history, recommend 3 books.
            {f'Additional criteria: {criteria}' if criteria else ''}
            
            Your response MUST be a valid JSON object with this exact structure:
            {{
                "books": [
                    {{
                        "title": "Book Title",
                        "author": ["Author Name"],
                        "price": 19.99,
                        "summary": "A brief summary of the book",
                        "purchase_links": {{
                            "amazon": "https://www.amazon.it/dp/actual-isbn-or-search-url",
                            "lafeltrinelli": "https://www.lafeltrinelli.it/actual-book-url"
                        }}
                    }}
                ]
            }}
            
            Rules:
            1. Always return exactly 3 books
            2. Use realistic book titles and authors
            3. Prices should be in euros (€)
            4. Summaries should be 1-2 sentences
            5. For purchase links:
               - Provide actual working links to Amazon.it and LaFeltrinelli.it
               - Use ISBN-based links when possible
               - If ISBN is not available, use search URLs that will definitely work
               - Make sure the links are current and valid
            6. The response must be valid JSON
            7. Consider the conversation history when making recommendations
            8. If specific criteria are provided (like language or publisher), ensure all recommended books meet those criteria"""
        }
    ]
    
    # Add relevant chat history context
    for msg in chat_history[-5:]:  # Use last 5 messages for context
        messages.append({"role": msg.role, "content": msg.content})
    
    messages.append({"role": "user", "content": query})
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7,
            max_tokens=1000
        )
        
        content = response.choices[0].message.content.strip()
        print("GPT Response:", content)  # Debug print
        
        # Try to parse the JSON response
        import json
        data = json.loads(content)
        
        # Validate the response structure
        if not isinstance(data, dict) or 'books' not in data:
            raise ValueError("Invalid response structure")
        
        books = data['books']
        if not isinstance(books, list) or len(books) == 0:
            raise ValueError("No books in response")
        
        # Validate and process each book
        processed_books = []
        for book in books:
            if not all(key in book for key in ['title', 'author', 'price', 'summary', 'purchase_links']):
                raise ValueError("Invalid book structure")
            
            # Process author list
            if not isinstance(book['author'], list):
                book['author'] = [book['author']]
            
            # Process price
            if not isinstance(book['price'], (int, float)):
                book['price'] = float(book['price'])
            
            # Fetch real links using GPT
            real_links = fetch_real_links(book['title'], book['author'][0] if book['author'] else "")
            book['purchase_links'] = real_links
            
            processed_books.append(book)
        
        return Output(books=processed_books)
    except Exception as e:
        print(f"Error in generate_response: {str(e)}")
        # Return some default books if there's an error
        return Output(books=[
            Book(
                title="The Great Gatsby",
                author=["F. Scott Fitzgerald"],
                price=12.99,
                summary="A story of the fabulously wealthy Jay Gatsby and his love for the beautiful Daisy Buchanan.",
                purchase_links={
                    "amazon": "https://www.amazon.it/Great-Gatsby-F-Scott-Fitzgerald/dp/0141182636",
                    "lafeltrinelli": "https://www.lafeltrinelli.it/libri/f-scott-fitzgerald/great-gatsby-9780141182636"
                }
            ),
            Book(
                title="1984",
                author=["George Orwell"],
                price=14.99,
                summary="A dystopian novel set in a totalitarian society where critical thought is suppressed.",
                purchase_links={
                    "amazon": "https://www.amazon.it/1984-George-Orwell/dp/0451524934",
                    "lafeltrinelli": "https://www.lafeltrinelli.it/libri/george-orwell/1984-9780451524935"
                }
            ),
            Book(
                title="To Kill a Mockingbird",
                author=["Harper Lee"],
                price=13.99,
                summary="The story of racial injustice and the loss of innocence in the American South.",
                purchase_links={
                    "amazon": "https://www.amazon.it/Kill-Mockingbird-Harper-Lee/dp/0446310786",
                    "lafeltrinelli": "https://www.lafeltrinelli.it/libri/harper-lee/kill-mockingbird-9780446310789"
                }
            )
        ])

@app.route('/chatbot', methods=['POST'])
def chatbot():
    try:
        data = request.get_json()
        query = data.get('query')
        session_id = data.get('session_id', 'default')
        
        if not query:
            return jsonify({"error": "No query provided"}), 400

        # Initialize or get chat history for this session
        if session_id not in chat_histories:
            chat_histories[session_id] = ChatHistory()
        
        chat_history = chat_histories[session_id]
        
        # Add user message to history
        chat_history.messages.append(Message(role="user", content=query))

        # First, check if this is a follow-up question about a previously recommended book
        if chat_history.last_recommended_books:
            matched_book = is_book_followup(query, chat_history.last_recommended_books)
            if matched_book:
                detailed_response = get_book_details(matched_book, query)
                chat_history.messages.append(Message(role="assistant", content=detailed_response))
                return jsonify({
                    "response": detailed_response,
                    "books": None,
                    "session_id": session_id
                })

        # Check if this is a follow-up with specific criteria
        if chat_history.last_query and is_criteria_followup(query, chat_history.last_query):
            response_text = "Here are some books matching your criteria:"
            answer = generate_response(chat_history.last_query, chat_history.messages, criteria=query)
            
            # Store the recommended books for future reference
            chat_history.last_recommended_books = [book.dict() for book in answer.books]
            
            chat_history.messages.append(Message(role="assistant", content=response_text))
            
            return jsonify({
                "response": response_text,
                "books": [book.dict() for book in answer.books],
                "session_id": session_id
            })

        is_book_related = analyze_query(query, chat_history.messages)
        print(f"Is book related? {is_book_related}")

        if not is_book_related:
            response_text = "I'm just a bookseller, I can help you find the next book to read but nothing else"
            chat_history.messages.append(Message(role="assistant", content=response_text))
            return jsonify({
                "response": response_text,
                "books": None,
                "session_id": session_id
            })
        else:
            response_text = "Here are some books you might like:"
            answer = generate_response(query, chat_history.messages)
            
            # Store the recommended books and query for future reference
            chat_history.last_recommended_books = [book.dict() for book in answer.books]
            chat_history.last_query = query
            
            chat_history.messages.append(Message(role="assistant", content=response_text))
            
            return jsonify({
                "response": response_text,
                "books": [book.dict() for book in answer.books],
                "session_id": session_id
            })
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)

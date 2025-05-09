"use client"
import { useState, useEffect, useRef } from 'react';
import { X, Bot, Send, LoaderCircle } from 'lucide-react';
import { cn } from '@/app/lib/utils';
import axios from 'axios';

interface Book {
  author: string[];
  price: number;
  summary: string;
  title: string;
  purchase_links: {
    amazon: string;
    lafeltrinelli: string;
  };
}

interface Message {
  text?: string;
  isBot: boolean;
  books?: Book[];
}

const ChatBot = () => {
  const [messages, setMessages] = useState<Message[]>([
    { text: "Hi there 👋\nHow can I help you today?", isBot: true }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [input]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = input.trim();
    setInput('');
    setMessages(prev => [...prev, { text: userMessage, isBot: false }]);
    setIsLoading(true);

    try {
      const response = await axios.post<{ 
        response: string;
        books?: Book[] 
      }>(
        'https://on-donkey-highly.ngrok-free.app/chatbot',
        { query: userMessage },
        {
          headers: { 
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          }
        }
      );

      setMessages(prev => [
        ...prev, 
        { 
          text: response.data.books ? undefined : response.data.response,
          isBot: true,
          books: response.data.books
        }
      ]);
    } catch (error) {
      console.error('Error:', error);
      setMessages(prev => [...prev, { 
        text: "Sorry, I'm having trouble responding.", 
        isBot: true 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className='flex justify-center items-center h-screen'>
      <div className="w-[860px] rounded-lg shadow-lg overflow-hidden">
        {/* Header */}
        <div className="bg-[#8359E3] p-4 flex justify-between items-center">
          <h2 className="text-white text-xl font-bold">Book Assistant</h2>
          <button 
            className="text-white hover:bg-[#724fd0] p-1 rounded-full transition-colors"
            aria-label="Close chat"
          >
            <X size={24} />
          </button>
        </div>

        {/* Messages */}
        <div className="bg-white h-[500px] overflow-y-auto p-4 space-y-4">
          {messages.map((message, index) => (
            <div
              key={index}
              className={cn(
                "flex items-start gap-2.5",
                !message.isBot && "flex-row-reverse"
              )}
            >
              {message.isBot && (
                <div className="w-8 h-8 rounded bg-[#8359E3] flex items-center justify-center">
                  <Bot className="text-white" size={18} />
                </div>
              )}
              <div
                className={cn(
                  "rounded-lg p-3",
                  message.isBot ? "bg-gray-100 max-w-[800px]" : "bg-[#8359E3] max-w-[360px]"
                )}
              >
                {/* Show text for all messages except bot messages with books */}
                {(message.text || (!message.books && message.isBot)) && (
                  <p className={cn(
                    "whitespace-pre-line",
                    message.isBot ? "text-black" : "text-white"
                  )}>
                    {message.text}
                  </p>
                )}
                
                {/* Display books if they exist */}
                {message.books && message.books.length > 0 && (
                  <div className="grid grid-cols-1 gap-3 mt-3">
                    {message.books.map((book, i) => (
                      <div key={i} className="border p-3 rounded-lg bg-white shadow-sm">
                        <h3 className="font-bold text-[#8359E3] text-[16px]">📕 {book.title}</h3>
                        <p className="text-[14px] text-black">👨‍⚕️ {book.author.join(', ')}</p>
                        <p className="text-[14px] font-bold text-[#8359E3]">💰 €{book.price.toFixed(2)}</p>
                        <p className="text-[14px] mt-1 text-black line-clamp-2">📚{book.summary}</p>
                        <div className="flex gap-2 mt-2">
                          <a 
                            href={book.purchase_links.amazon} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="flex-1 bg-[#FF9900] text-white text-center py-2 px-4 rounded-lg hover:bg-[#E68A00] transition-colors"
                          >
                            Buy on Amazon
                          </a>
                          <a 
                            href={book.purchase_links.lafeltrinelli} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="flex-1 bg-[#8359E3] text-white text-center py-2 px-4 rounded-lg hover:bg-[#724fd0] transition-colors"
                          >
                            Buy on LaFeltrinelli
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          
          {isLoading && (
            <div className="flex items-start gap-2.5">
              <div className="w-8 h-8 rounded bg-[#8359E3] flex items-center justify-center">
                <Bot className="text-white" size={18} />
              </div>
              <div className="bg-gray-100 rounded-lg p-3">
                <LoaderCircle className="w-5 h-5 animate-spin text-[#8359E3]" />
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <form onSubmit={handleSubmit} className="bg-white border-t p-4">
          <div className="flex gap-2">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="What books are you looking for? (Press Enter to send, Shift+Enter for new line)"
              className="flex-1 border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-[#8359E3] text-black resize-none min-h-[80px] max-h-[120px]"
              disabled={isLoading}
              rows={3}
            />
            <button
              type="submit"
              className="bg-[#8359E3] text-white p-2 rounded-lg hover:bg-[#724fd0] transition-colors disabled:opacity-50 self-end"
              disabled={!input.trim() || isLoading}
            >
              <Send size={20} />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ChatBot;
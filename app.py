from flask import Flask, render_template, jsonify, request, url_for
import requests
from transformers import pipeline
from newspaper import Article
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Initialize the summarization pipeline
pipe = pipeline("summarization", model="facebook/bart-large-cnn")

# API key from environment variable
api_key = os.getenv("API_KEY")  
# Function to fetch articles from NewsAPI by category
def fetch_articles(api_key, category="general", page=1):
    url = f"https://newsapi.org/v2/top-headlines?category={category}&apiKey={api_key}&pageSize=20&page={page}"
    response = requests.get(url)
    articles = response.json().get("articles", [])
    return articles

def chunk_text_with_context(text, context, max_tokens=500):
    words = text.split()
    chunks = []
    current_chunk = [context]
    current_length = len(pipe.tokenizer.encode(context, add_special_tokens=False))

    for word in words:
        word_length = len(pipe.tokenizer.encode(word, add_special_tokens=False))
        if current_length + word_length <= max_tokens:
            current_chunk.append(word)
            current_length += word_length
        else:
            chunks.append(" ".join(current_chunk))
            current_chunk = [context, word]
            current_length = len(pipe.tokenizer.encode(context, add_special_tokens=False)) + word_length

    # Add the last chunk if there's any
    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


# Function to summarize the article content using the BART model
def summarize_article(article_url):
    try:
        article = Article(article_url)
        article.download()
        article.parse()
        article_text = article.text

        # Only summarize if the article is longer than 100 words
        if len(article_text.split()) < 100:
            return None  # Skip if article is too short
        print(f"Article length: {len(article_text.split())}")

        # return article_text

        chunks = chunk_text_with_context(article_text, article.title, 1000)

        # Generate summary with minimum length of 60 words
        summary_result = pipe(chunks, max_length=80, min_length=60)
        print(summary_result)
        summary = " ".join([s["summary_text"] for s in summary_result])
        
       

        return summary

    except Exception as e:
        print(f"Error summarizing article: {e}, URL: {article_url}")
        return None

# Route to handle displaying news articles from a category
@app.route('/category/<category>', methods=['GET'])
def category_page(category="general"):
    articles = fetch_articles(api_key, category)
    summaries = []
    urls_seen = set()  # Track URLs to avoid repetition
    for article in articles:
        article_url = article['url']
        if article_url in urls_seen:
            continue  # Skipping the  repeated articles
        image_url = article.get('urlToImage')
        try:
            summary = summarize_article(article_url)
            if summary:  # Only add if a valid summary is generated
                summaries.append({
                    'title': article['title'],
                    'summary': summary,
                    'image_url': image_url,
                    'url': article_url
                })
                urls_seen.add(article_url)
        except Exception as e:
            print(f"Error summarizing article: {e}")

    
    return render_template('category_page.html', articles=summaries, category=category.capitalize())

# Route for the homepage, defaulting to the "general" category
@app.route('/')
def index():
    return category_page("general")


@app.route('/load_more/<category>/<int:page>', methods=['GET'])
def load_more_articles(category="general", page=1):
    articles = fetch_articles(api_key, category, page)
    summaries = []
    urls_seen = set()
    for article in articles:
        article_url = article['url']
        if article_url in urls_seen:
            continue  # Avoid repeated articles
        image_url = article.get('urlToImage')
        try:
            summary = summarize_article(article_url)
            if summary:  # Only add if valid summary is generated
                summaries.append({
                    'title': article['title'],
                    'summary': summary,
                    'image_url': image_url,
                    'url': article_url
                })
                urls_seen.add(article_url)
        except Exception as e:
            print(f"Error summarizing article: {e}")

    return jsonify({'articles': summaries})

if __name__ == "__main__":
    app.run(debug=True)

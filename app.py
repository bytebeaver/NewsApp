# from flask import Flask, render_template, jsonify, request, url_for
# import requests
# from transformers import pipeline
# from newspaper import Article
# import os
# from dotenv import load_dotenv


# load_dotenv()

# app = Flask(__name__)

# # Initialize the summarization pipeline
# pipe = pipeline("summarization", model="facebook/bart-large-cnn")


# api_key = os.getenv("API_KEY")  

# def fetch_articles(api_key, category="general", page=1):
#     url = f"https://newsapi.org/v2/top-headlines?category={category}&apiKey={api_key}&pageSize=10&page={page}"
#     response = requests.get(url)
#     articles = response.json().get("articles", [])
#     return articles

# def chunk_text_with_context(text, context, max_tokens=500):
#     words = text.split()
#     chunks = []
#     current_chunk = [context]
#     current_length = len(pipe.tokenizer.encode(context, add_special_tokens=False))

#     for word in words:
#         word_length = len(pipe.tokenizer.encode(word, add_special_tokens=False))
#         if current_length + word_length <= max_tokens:
#             current_chunk.append(word)
#             current_length += word_length
#         else:
#             chunks.append(" ".join(current_chunk))
#             current_chunk = [context, word]
#             current_length = len(pipe.tokenizer.encode(context, add_special_tokens=False)) + word_length

 
#     if current_chunk:
#         chunks.append(" ".join(current_chunk))

#     return chunks



# def summarize_article(article_url):
#     try:
#         article = Article(article_url)
#         article.download()
#         article.parse()
#         article_text = article.text

#         # not summarizing small articles 
#         if len(article_text.split()) < 100:
#             return None  # Skip if article is too short
#         print(f"Article length: {len(article_text.split())}")

        

#         chunks = chunk_text_with_context(article_text, article.title, 1000)

#         # 60 word summary

#         summary_result = pipe(chunks, max_length=80, min_length=60)
#         print(summary_result)
#         summary = " ".join([s["summary_text"] for s in summary_result])
#         return summary

#     except Exception as e:
#         print(f"Error summarizing article: {e}, URL: {article_url}")
#         return None

# # Route to handle displaying news articles from a category
# @app.route('/category/<category>', methods=['GET'])
# def category_page(category="general"):
#     articles = fetch_articles(api_key, category)
#     summaries = []
#     urls_seen = set()  # Track URLs to avoid repetition
#     for article in articles:
#         article_url = article['url']
#         if article_url in urls_seen:
#             continue  # Skipping the  repeated articles
#         image_url = article.get('urlToImage')
#         try:
#             summary = summarize_article(article_url)
#             if summary:  # Only add if a valid summary is generated
#                 summaries.append({
#                     'title': article['title'],
#                     'summary': summary,
#                     'image_url': image_url,
#                     'url': article_url
#                 })
#                 urls_seen.add(article_url)
#         except Exception as e:
#             print(f"Error summarizing article: {e}")

    
#     return render_template('category_page.html', articles=summaries, category=category.capitalize())


# @app.route('/')
# def index():
#     return category_page("general")


# @app.route('/load_more/<category>/<int:page>', methods=['GET'])
# def load_more_articles(category="general", page=1):
#     articles = fetch_articles(api_key, category, page)
#     summaries = []
#     urls_seen = set()
#     for article in articles:
#         article_url = article['url']
#         if article_url in urls_seen:
#             continue  # Avoid repeated articles
#         image_url = article.get('urlToImage')
#         try:
#             summary = summarize_article(article_url)
#             if summary:  # Only add if valid summary is generated
#                 summaries.append({
#                     'title': article['title'],
#                     'summary': summary,
#                     'image_url': image_url,
#                     'url': article_url
#                 })
#                 urls_seen.add(article_url)
#         except Exception as e:
#             print(f"Error summarizing article: {e}")

#     return jsonify({'articles': summaries})

# if __name__ == "__main__":
#     app.run(debug=True)







from flask import Flask, render_template, jsonify, request, url_for, redirect, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import requests
from transformers import pipeline
from newspaper import Article
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key') 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///news.db'
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


pipe = pipeline("summarization", model="facebook/bart-large-cnn")
api_key = os.getenv("API_KEY")


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    preferences = db.relationship('UserPreference', backref='user', lazy=True)

class UserPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    country = db.Column(db.String(2))
    city = db.Column(db.String(100))

class SummaryTable(db.Model):
    id = db.Column(db.String(256), primary_key=True)
    summary = db.Column(db.String(5000))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def chunk_text_with_context(text, title, max_tokens=500):
    """
    Split text into chunks while maintaining context from the title.
    
    Args:
        text (str): The main text to be chunked
        title (str): The title to be used as context
        max_tokens (int): Maximum number of tokens per chunk
    
    Returns:
        list: List of text chunks with context
    """
    words = text.split()
    chunks = []
    current_chunk = [title]  # Use title as context
    current_length = len(pipe.tokenizer.encode(title, add_special_tokens=False))

    for word in words:
        word_length = len(pipe.tokenizer.encode(word, add_special_tokens=False))
        if current_length + word_length <= max_tokens:
            current_chunk.append(word)
            current_length += word_length
        else:
            chunks.append(" ".join(current_chunk))
            current_chunk = [title, word]  # Reset chunk with title as context
            current_length = len(pipe.tokenizer.encode(title, add_special_tokens=False)) + word_length

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks

def summarize_article(article_url):
    try:
        summ = SummaryTable.query.filter_by(id=article_url).first()
        if summ:
            return summ.summary
        article = Article(article_url)
        article.download()
        article.parse()
        article_text = article.text

        # not summarizing small articles 
        if len(article_text.split()) < 100:
            return None  # Skip if article is too short
        print(f"Article length: {len(article_text.split())}")

        # Use article title as context when chunking
        chunks = chunk_text_with_context(article_text, article.title, 1000)

        # 60 word summary
        summary_result = pipe(chunks, max_length=80, min_length=60)
        print(summary_result)
        summary = " ".join([s["summary_text"] for s in summary_result])
        summ = SummaryTable(id=article_url, summary=summary)
        db.session.add(summ)
        db.session.commit()
        
        return summary

    except Exception as e:
        print(f"Error summarizing article: {e}, URL: {article_url}")
        return None

    

def fetch_articles(api_key, category="general", page=1, country=None, q=None):
    # base_url = "https://newsapi.org/v2/top-headlines"
    base_url = "https://newsapi.org/v2/top-headlines"
    params = {
        "apiKey": api_key,
        "category": category,
        "pageSize": 10,
        "page": page
    }
    
    if country:
        params["country"] = country
    if q:
        params["q"] = q

    print(params)
        
    response = requests.get(base_url, params=params)
    print(response.json())
    return response.json().get("articles", [])

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid username or password')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
            
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/preferences', methods=['GET', 'POST'])
@login_required
def preferences():
    if request.method == 'POST':
        # Clear existing preferences
        UserPreference.query.filter_by(user_id=current_user.id).delete()
        
        # Add new preferences
        categories = request.form.getlist('categories')
        country = request.form.get('country')
        city = request.form.get('city')
        
        for category in categories:
            pref = UserPreference(
                user_id=current_user.id,
                category=category,
                country=country,
                city=city
            )
            db.session.add(pref)
            
        db.session.commit()
        flash('Preferences updated successfully!')
        return redirect(url_for('index'))
        
    user_prefs = UserPreference.query.filter_by(user_id=current_user.id).first()
    return render_template('preferences.html', preferences=user_prefs)

@app.route('/search')
@login_required
def search():
    query = request.args.get('q', '')
    if query:
        articles = fetch_articles(api_key, q=query)
        processed_articles = []
        for article in articles:
            try:
                summary = summarize_article(article['url'])
                if summary:
                    processed_articles.append({
                        'title': article['title'],
                        'summary': summary,
                        'image_url': article.get('urlToImage'),
                        'url': article['url']
                    })
            except Exception as e:
                print(f"Error processing article: {e}")
        return render_template('search_results.html', articles=processed_articles, query=query)
    return render_template('search_results.html', articles=[])

@app.route('/')
@login_required
def index():
    user_prefs = UserPreference.query.filter_by(user_id=current_user.id).first()
    if user_prefs:
        return category_page(user_prefs.category, user_prefs.country)
    return category_page("general")

@app.route('/category/<category>')
@login_required
def category_page(category="general", country=None):
    articles = fetch_articles(api_key, category, country=country)
    processed_articles = []
    for article in articles:
        try:
            summary = summarize_article(article['url'])
            if summary:
                processed_articles.append({
                    'title': article['title'],
                    'summary': summary,
                    'image_url': article.get('urlToImage'),
                    'url': article['url']
                })
        except Exception as e:
            print(f"Error processing article: {e}")
    return render_template('category_page.html', 
                         articles=processed_articles, 
                         category=category.capitalize())

@app.route('/load_more/<category>/<int:page>')
@login_required
def load_more_articles(category="general", page=1):
    user_prefs = UserPreference.query.filter_by(user_id=current_user.id).first()
    country = user_prefs.country if user_prefs else None
    
    articles = fetch_articles(api_key, category, page, country)
    processed_articles = []
    for article in articles:
        try:
            summary = summarize_article(article['url'])
            if summary:
                processed_articles.append({
                    'title': article['title'],
                    'summary': summary,
                    'image_url': article.get('urlToImage'),
                    'url': article['url']
                })
        except Exception as e:
            print(f"Error processing article: {e}")
    return jsonify({'articles': processed_articles})

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
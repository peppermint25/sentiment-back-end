from flask import Flask, request, jsonify, session, redirect
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt
from flask_cors import CORS, cross_origin
from functools import wraps
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson.json_util import dumps
from bson import json_util
from bs4 import BeautifulSoup
import requests
import openai
import json
import os
import bcrypt
from api_keys import open_ai_key
from datetime import datetime

# Set OpenAI API key

openai.api_key = open_ai_key

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.urandom(24)
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = False
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_USE_SIGNER'] = True
app.config['SECRET_KEY'] = os.urandom(24)

jwt = JWTManager(app)
CORS(app, supports_credentials=True)


client = MongoClient("mongodb://db:27017/")
database = client.user
collection = database.history
userCollection = database.users

@app.route('/api/scrape-url', methods=['POST'])
@jwt_required()
def scrape_url():
    try:
        user_id = get_jwt_identity()
        data = request.json
        article_url = data.get('article_url')
        article_subject = data.get('article_subject')
        
        # Scrape title and content from the URL here.
        content = scrape_article(article_url)
        
        if content is None:
            return jsonify({'message': "The provided URL can't get analysed, you have to select the text option and copy and paste the contents of the website"})
        
        # Send the scraped data to the AI model.
        sentiment = analyze_sentiment(article_subject, content)  # Implement this function.
        
        if sentiment is None:
            return jsonify({'message': 'Error while analyzing sentiment.'})
        
        save_to_db(user_id, article_subject, sentiment, article_url)
        
        # Return the AI result.
        return jsonify({'sentiment': sentiment, 'title': article_subject})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/scrape-text', methods=['POST'])
@jwt_required()
def scrape_text():
    try:
        user_id = get_jwt_identity()
        data = request.json
        copied_text = data.get('article_text')
        article_subject = data.get('article_subject')
        
        # Send the copied text directly to the AI model.
                
        sentiment = analyze_sentiment(article_subject ,copied_text)
        
        if sentiment is None:
            return jsonify({'message': 'Error while analyzing sentiment.'})
        
        
        save_to_db(user_id, article_subject, sentiment, copied_text)

        # Return the AI result.
        return jsonify({'sentiment': sentiment, 'title': article_subject})
    except Exception as e:
        return jsonify({'error': str(e)})
    
@app.route('/api/history', methods=['GET'])
@jwt_required()
def get_history():
    try:
        user_id = get_jwt_identity()
        print("user id", user_id)
        documents = collection.find({'user_id': user_id}).sort('timestamp', -1)
        # documents = collection.find().sort('timestamp', -1)
        json_data = json.loads(dumps(documents, default=json_util.default))
        return jsonify(json_data)
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/api/history/<document_id>', methods=['GET'])
@jwt_required()
def get_document(document_id):
    try:
        document = collection.find_one({'_id': ObjectId(document_id)})
        json_data = json.loads(dumps(document, default=json_util.default))
        return jsonify(json_data)
    except Exception as e:
        return jsonify({'error': str(e)})
    
@app.route('/api/history/<document_id>', methods=['DELETE'])
@jwt_required()
def delete_document(document_id):
    try:
        # Delete the document from the collection
        delete_by_id(document_id)
        return jsonify({'message': 'Document deleted successfully.'})
    except Exception as e:
        return jsonify({'error': str(e)})
    
@app.route('/api/history', methods=['DELETE'])
@jwt_required()
def delete_all():
    try:
        # Delete the document from the collection
        collection.delete_many({})
        return jsonify({'message': 'All documents deleted successfully.'})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/history/search/<search_term>', methods=['GET'])
@jwt_required()
def search_history(search_term):
    try:
        user_id = get_jwt_identity()
        documents = collection.find({'user_id': user_id, 'subject': {'$regex': search_term, '$options': 'i'}}).sort('timestamp', -1)
        json_data = json.loads(dumps(documents, default=json_util.default))
        return jsonify(json_data)
    except Exception as e:
        return jsonify({'error': str(e)})
   
@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'message': 'Email or password is empty.'})
        
        # Check if username already exists
        user = userCollection.find_one({'email': email})
        if user:
            return jsonify({'message': 'An account with this email already exists.'})
        
        hashedPassword = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Create the user document
        document = {
            'email': email,
            'password': hashedPassword.decode('utf-8')
        }
        userCollection.insert_one(document)
                
        return jsonify({'message': 'User created successfully.'})
    except Exception as e:
        return jsonify({'error': str(e)})
    
@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    user = userCollection.find_one({'email': email})

    if not user:
        return jsonify({'message': 'Incorrect email or password. Please check your credentials and try again.'})

    user_id = str(user['_id'])  # Use the unique ID from the user document

    print('user ' + user_id)

    hashed_password = user['password'].encode('utf-8')
    if bcrypt.checkpw(password.encode('utf-8'), hashed_password):
        # If the password is correct, create and return an access token
        access_token = create_access_token(identity=user_id)

        return jsonify({'token': access_token, 'user_id': user_id})
    else:
        return jsonify({'message': 'Incorrect email or password. Please check your credentials and try again.'})


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    return jsonify({'message': 'Logged out successfully.'})

@app.route('/api/auth/delete', methods=['DELETE'])
@jwt_required()
def delete_user():
    try:
        user_id = get_jwt_identity()
        userCollection.delete_one({'_id': ObjectId(user_id)})
        collection.delete_many({'user_id': user_id})
        return jsonify({'message': 'User deleted successfully.'})
    except Exception as e:
        return jsonify({'error': str(e)})
    
@app.route('/api/auth/change-password', methods=['POST'])
@jwt_required()
def change_password():
    try:
        user_id = get_jwt_identity()
        data = request.json
        old_password = data.get('old_password')
        new_password = data.get('new_password')
        
        if not old_password or not new_password:
            return jsonify({'message': 'Old or new password is empty.'})
        
        user = userCollection.find_one({'_id': ObjectId(user_id)})
        
        hashed_password = user['password'].encode('utf-8')
        if bcrypt.checkpw(old_password.encode('utf-8'), hashed_password):
            # If the password is correct, create and return an access token
            hashedPassword = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
            userCollection.update_one({'_id': ObjectId(user_id)}, {'$set': {'password': hashedPassword.decode('utf-8')}})
            return jsonify({'message': 'Password changed successfully.'})
        else:
            return jsonify({'message': 'Incorrect password.'})
    except Exception as e:
        return jsonify({'error': str(e)})

def scrape_article(url):

    response = requests.get(url)
    response.raise_for_status()    
    soup = BeautifulSoup(response.text, 'html.parser')
    article = soup.find('article')
    if article:
        content = article.get_text()
    else:
        return None
        
    return content


def analyze_sentiment(subject ,text):
    try:
        # Define your article content as a variable
        article_subject = subject
        article_content = text

        # Create the prompt with the variable
        
        prompt = f"""
        There is a Subject and a article. Analyze the sentiment of how the "Subject" is mentioned in the article. Examine each mention if it is Positive/Neutral/Negative, there can multiple of each of those.
        It should be only strictly about the Subject only, not an opinion expresed by the subject, just strictly about the Subject, don't examine the sentiment of things unrelated to the subject.
        Avoid having duplicate mentions or mentions of things unrelated to the subject.
        "sentiment_text" must contain the subject.
        If two "sentiment_texts" are really similar and so are their "explanations" you can try and combine the them. There need to be explanations, why that piece of text is that sentiment.
        
        Provide each analysis in JSON array format with the structure "sentiment" (Capitalize the first letter),  "sentiment_text (First letter of the sentance is uppercase, 4 to 12 words)," and "explanation (Explain why it is that sentiment, not just saying that it is that sentiment, don't use the words "this mention" or similar, just exlain why the "sentiment_text" is that sentiment using info from the rest of the article or from what you know)" (if there is any kind of error output it in the format "message": "error text"):

        Subject: <{article_subject}>
        Article about the subject: "{article_content}"
        """
        
        response = get_completion(prompt)
        
        print("response", response)
                
        json_response = convert_to_json(response)

        return json_response 

    except Exception as e:
        return str(e)

def get_completion(prompt, model="gpt-3.5-turbo"):
    messages = [{"role": "user", "content": prompt}]
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=0,
    )
    return response.choices[0].message["content"]

def convert_to_json(response):
    try:
        json_response = json.loads(response)
        return json_response
    except Exception as e:
        return None


def save_to_db(user_id, subject, sentiment_data, article):
    try:                        
        current_time = datetime.utcnow().timestamp() * 1000  # Convert to milliseconds
        document = {
            'user_id': user_id,
            'subject': subject,
            'sentiment': sentiment_data,
            'timestamp': current_time,
            'article': article
        }
        collection.insert_one(document)
        return True  # Indicates success
    except Exception as e:
        return str(e)  # Return error message on failure

def get_history():
    try:
        documents = collection.find().sort('timestamp', -1)
        json_data = json.loads(dumps(documents, default=json_util.default))
        return jsonify(json_data)
    except Exception as e:
        return str(e)
    
def delete_by_id(documents):
    try:
        # Delete the document from the collection
        collection.delete_one({'_id': ObjectId(documents)})
        return True  # Indicates success
    except Exception as e:
        return str(e)  # Return error message on failure

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

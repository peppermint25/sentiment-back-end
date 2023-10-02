from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson.json_util import dumps
from bson import json_util
from bs4 import BeautifulSoup
import requests
import logging
from flask_cors import CORS, cross_origin
import openai
import json

openai.api_key = "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"

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

client = MongoClient("mongodb://db:27017/")
database = client.user
collection = database.history

CORS(app, resources={r"/api/scrape-url": {"origins": "*"}, r"/api/scrape-text": {"origins": "*"}})

@app.route('/api/scrape-url', methods=['POST'])
@cross_origin()  # Enable CORS for this route
def scrape_url():
    try:
        data = request.json
        article_url = data.get('article_url')
        article_subject = data.get('article_subject')
        
        if not article_url:
            return jsonify({'message': 'URL received, but it was empty.'})

        # Check if article_url is a valid URL before making the request.
        if not article_url.startswith(('http://', 'https://')):
            return jsonify({'message': 'Invalid URL format.'})

        # Scrape title and content from the URL here.
        content = scrape_article(article_url)
        
        # Send the scraped data to the AI model.
        sentiment = analyze_sentiment(article_subject, content)  # Implement this function.
        
        save_to_db(article_subject, sentiment)
        
        # Return the AI result.
        return jsonify({'sentiment': sentiment, 'title': article_subject})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/scrape-text', methods=['POST'])
@cross_origin()  # Enable CORS for this route
def scrape_text():
    try:
        data = request.json
        copied_text = data.get('article_text')
        article_subject = data.get('article_subject')
        
        if not copied_text:
            return jsonify({'message': 'Text received, but it was empty.'})

        # Send the copied text directly to the AI model.
                
        sentiment = analyze_sentiment(article_subject ,copied_text)
        
        save_to_db(article_subject, sentiment)

        # Return the AI result.
        return jsonify({'sentiment': sentiment, 'title': article_subject})
    except Exception as e:
        return jsonify({'error': str(e)})

def scrape_article(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        article = soup.find('article')
        if article:
            content = article.get_text()
        else:
            content = "Unable to scrape"
            
        return content
    except Exception as e:
        # Log the exception for debugging purposes.
        logging.error("Error while scraping article: %s", str(e))
        return '', ''  # Return default values in case of an error.  # Return default values in case of an error.

def analyze_sentiment(subject ,text):
    try:
        # Define your article content as a variable
        article_subject = subject
        article_content = text

        # Create the prompt with the variable
        
        prompt = f"""
        There is a Subject and a article. Analyze the sentiment of how the "subject" is mentioned in the article. Examine each mention if it is Positive/Neutral/Negative, there can multiple of each of those. Avoid having duplicate mentions or mentions of things unrelated to the subject.S If two "sentiment_texts" are really similar and so are their "explanations" you can try and combine the them. There need to be proper explanations, why that piece of text is that sentiment. Provide each analysis in JSON array format with the structure "sentiment" (Capitalize the first letter),  "sentiment_text (First letter of the sentance is uppercase, 4 to 12 words)," and "explanation (Explain why it is that sentiment, not just saying that it is that sentiment, don't use the words "this mention" or similar, just exlain why the "sentiment_text" is that sentiment using info from the rest of the article or from what you know)":

        Subject: <{article_subject}>
        Article about the subject: "{article_content}"
        """

        response = get_completion(prompt)
    
        print(response)
        
        json_response = json.loads(response)

        print (json_response)

        return json_response 

    except Exception as e:
        return str(e)

# Implement this function to send data to the AI model.
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
        return str(e)


def save_to_db(subject, sentiment_data):
    try:
        
        print("Saving to db")
        # Create a document for each sentiment entry and insert it into the collection
        for sentiment_entry in sentiment_data:
            document = {
                'subject': subject,
                'sentiment': sentiment_entry['sentiment'],
                'sentiment_text': sentiment_entry['sentiment_text'],
                'explanation': sentiment_entry['explanation']
            }
            print(document)
            collection.insert_one(document)
        
        return True  # Indicates success
    except Exception as e:
        return str(e)  # Return error message on failure

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

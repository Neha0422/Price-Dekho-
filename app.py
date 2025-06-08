from flask import Flask, render_template, request, flash, redirect, url_for
import requests
from bs4 import BeautifulSoup
from fuzzywuzzy import fuzz, process
from pymongo import MongoClient
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import joblib
from datetime import datetime, timedelta
import threading
import schedule
import time
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from apscheduler.schedulers.background import BackgroundScheduler
import random


app = Flask(__name__)
app.config['SCHEDULER_STARTED'] = False
app.secret_key = "9f3b6e739bb45d1b59c8c7d097b7b7b1"

import os
os.environ['SENDGRID_API_KEY'] = 'enter your sengridAPI with registered email'



# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["price_dekho"]
collection = db["product_prices"]
alerts_collection = db["alerts"]
#alerts_collection.delete_many({})

#if alerts_collection.count_documents({}) == 0:
    #print("No alerts found in the collection.")
#else:
    # Fetch and display all alerts
    #for alert in alerts_collection.find():
        #print(alert)

user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
    # Add more User-Agents here
]


# Function to scrape Amazon
def scrape_amazon(search_query, max_pages=5):
    search_query = search_query.replace(" ", "+")
    base_url = f"https://www.amazon.in/s?k={search_query}"
    headers = {
        'User-Agent': random.choice(user_agents),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.google.com/"
    }

    products = []
    
    for page in range(1, max_pages + 1):
        url = f"{base_url}&page={page}"
        print("Amazon request URL:", url)
        response = requests.get(url, headers=headers)
         # Check for successful request
        if response.status_code != 200:
            print(f"Error: Unable to fetch Amazon page {page}")
            continue

        url = f"https://www.amazon.in/s?k={search_query.replace(' ', '+')}&page={page}"
        soup = BeautifulSoup(response.text, "html.parser")

        for item in soup.find_all("div", class_="s-card-container") or soup.find_all("div", class_="sg-col-inner"):
            title_tag = item.find("h2")
            price_tag = item.find("span", class_="a-price-whole")
            image_tag = item.find("img", class_="s-image")
            url_tag = item.find("a", class_="a-link-normal", href=True)
            
            review_tag = item.find("span", class_="a-icon-alt")
            
            review_count_tag = item.find("span", class_="a-size-base a-color-secondary")

            desc_elem = item.find("div", class_="a-row a-size-base a-color-secondary")  # try an alternate tag for short desc
            if title_tag and url_tag:
                title = title_tag.text.strip()
                if price_tag:
                    price_text = price_tag.text.replace(",", "").strip()
                    try:
                        price = int(float(price_text))
                    except ValueError:
                        price = None
                else:
                    price = None

                image = image_tag["src"] if image_tag else "static/default.jpg"
                product_url = f"https://www.amazon.in{url_tag['href']}"
                reviews = "No Reviews"
                if review_tag:
                    reviews = review_tag.text.strip()

                review_count = "Not Available"
                if review_count_tag:
                    review_count = review_count_tag.text.strip()

                description = desc_elem.get_text().strip() if desc_elem else "No description available"
                

                products.append({"name": title, "price": price_text, "image": image, "link": product_url, "reviews": reviews, "amazon_description": description, "platform": "Amazon"})
        time.sleep(random.uniform(1, 3)) 
    print(f"✅ Total Amazon products scraped: {len(products)}")
    for product in products:
        print(f"Product: {product['name']}")
        print(f"Review: {product['reviews']}")
        print("Description:", description)
        print("-" * 50)


    return products


# Function to scrape Flipkart
def scrape_flipkart(search_query, max_pages=5):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36" ,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.google.com/"
    }

    products = []
    url = None 
    for page in range(1, max_pages + 1):

        url = f"https://www.flipkart.com/search?q={search_query.replace(' ', '+')}&page={page}"
        print(f"Flipkart request URL: {url}")

        response = requests.get(url, headers=headers)
        # Check for successful request
        if response.status_code != 200:
            print(f"Error: Unable to fetch Flipkart page {page}")
            continue

        soup = BeautifulSoup(response.text, "html.parser")

        for item in soup.find_all("div", class_="cPHDOP col-12-12"):
            title_tag = item.find("div", "a", class_=["KzDlHZ","WKTcLC BwBZT","syl9yP","wjcEIp","WKTcLC"]) 
            price_tag = item.find("div", class_=["Nx9bqj","Nx9bqj _4b5DiR"])
            image_tag = item.find("img", class_=["DByuf4","_53J4C-"]) 
            url_tag = item.find("a", class_=["CGtC98","rPDeLR","VJA3rP","wjcEIp","+tlBoD","WKTcLC BwBZT"], href=True) 
            review_tag = item.find("div", class_=["_2_R_DZ", "_1l3xXv", "XQDdHH"])  # Add more classes for consistency

            # Fallback in case it's not found
            if not review_tag:
                review_tag = item.find("span", class_="s1Q9rs")  # Some items have this class for reviews


            if title_tag and url_tag:
                title = title_tag.text.strip()
                if price_tag:
                    price_text = price_tag.text.replace("₹", "").replace(",", "").strip() 
                    try:
                        price = int(float(price_text))
                    except ValueError:
                        price = None
                else:
                    price = None

                image = image_tag["src"] if image_tag else "static/default.jpg"
                product_url = f"https://www.flipkart.com{url_tag['href']}"
                reviews = review_tag.text.strip() if review_tag else "No Reviews"
                

                products.append({"name": title, "price": price_text, "image": image, "link": product_url, "reviews": reviews, "platform": "Flipkart"}) 
        time.sleep(random.uniform(1, 3)) 
    print(f"✅ Total Flipkart products scraped: {len(products)}")
    return products

def clean_price(price):
    if price is None:
        return None
    return float(price.replace("₹", "").replace(",", "").strip())


# Compare prices from Amazon & Flipkart
def compare_prices(amazon_products, flipkart_products):
    results = []
    amazon_dict = {p["name"]: p for p in amazon_products}
    flipkart_dict = {p["name"]: p for p in flipkart_products}
    matched_amazon = set()
    matched_flipkart = set()

    # Match products with fuzzy logic
    for amz_title, amz_data in amazon_dict.items():
        match = process.extractOne(amz_title, flipkart_dict.keys(), scorer=fuzz.token_sort_ratio)
        
        if match and match[1] > 70:
            fk_title = match[0]
            fk_data = flipkart_dict[fk_title]

            amz_price = amz_data["price"]
            fk_price = fk_data["price"]

            amz_review = amz_data["reviews"]
            fk_review = fk_data["reviews"]

            # Clean price strings to float for correct comparison
            def clean_price(price):
                if price is None:
                    return None
                return float(price.replace("₹", "").replace(",", "").strip())

            amz_clean_price = clean_price(amz_price)
            fk_clean_price = clean_price(fk_price)

    # Accurate platform suggestion logic
            if amz_clean_price is not None and fk_clean_price is not None:
                best_platform = "Amazon" if amz_clean_price < fk_clean_price else "Flipkart"
            elif fk_clean_price is None and amz_clean_price is not None:
                best_platform = "Amazon"
            elif amz_clean_price is None and fk_clean_price is not None:
                best_platform = "Flipkart"
            else:
                best_platform = "Unknown"


            results.append({
        "name": amz_title,
        "amazon_price": amz_price,
        "flipkart_price": fk_price,
        "amazon_link": amz_data["link"],
        "flipkart_link": fk_data["link"],
        "amazon_image": amz_data["image"],
        "flipkart_image": fk_data["image"],
        "amazon_reviews": amz_review,
        "flipkart_reviews": fk_review,
        "best_platform": best_platform
            })
            matched_amazon.add(amz_title)
            matched_flipkart.add(fk_title)

    for amz_title, amz_data in amazon_dict.items():
        if amz_title not in matched_amazon:
            results.append({
            "name": amz_title,
            "amazon_price": amz_data["price"],
            "flipkart_price": None,
            "amazon_link": amz_data["link"],
            "flipkart_link": None,
            "amazon_image": amz_data["image"],
            "flipkart_image": None,
            "amazon_reviews": amz_data["reviews"],
            "flipkart_reviews": "No Reviews",
            "best_platform": "Amazon Only"
        })
            
    for fk_title, fk_data in flipkart_dict.items():
        if fk_title not in matched_flipkart:
            results.append({
                "name": fk_title,
                "amazon_price": None,
                "flipkart_price": fk_data["price"],
                "amazon_link": None,
                "flipkart_link": fk_data["link"],
                "amazon_image": None,
                "flipkart_image": fk_data["image"],
                "amazon_reviews": "No Reviews",
                "flipkart_reviews": fk_data["reviews"],
                "best_platform": "Flipkart Only"
            })

    return results

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        search_query = request.form["product"]
        amazon_products = scrape_amazon(search_query)
        flipkart_products = scrape_flipkart(search_query)
        comparison_results = compare_prices(amazon_products, flipkart_products)
        
        return render_template("index.html", products=comparison_results, query=search_query)

    return render_template("index.html", products=[])

def predict_price(product_name):
    # Get prices from Amazon & Flipkart
    amazon_data = scrape_amazon(product_name)
    flipkart_data = scrape_flipkart(product_name)

    # Initialize result lists for Amazon and Flipkart
    amazon_predictions = []
    flipkart_predictions = []

    # Process Amazon products
    for product in amazon_data:
        if product.get("price") is None:
            continue  # Skip if no price

        # Store current price in DB
        today = datetime.today()
        last_month = today - timedelta(days=30)
        collection.insert_one({
            "product_name": product["name"],
            "date": today,
            "price": product["price"],
            "platform": "Amazon"
        })

        # Fetch past prices for this product (Amazon only)
        prices_data = list(collection.find({
            "product_name": product["name"],
            "platform": "Amazon",
            "date": {"$gte": last_month}
        }).sort("date", 1))

        future_amazon_price = "No Data"
        if prices_data:
            # Prepare data
            dates = [(p["date"] - last_month).days for p in prices_data]
            prices = [p["price"] for p in prices_data]

            # Train model
            model = LinearRegression()
            X = np.array(dates).reshape(-1, 1)
            y = np.array(prices)
            model.fit(X, y)

            # Predict next price (3 days later)
            future_dates = np.array([[max(dates) + 3]])
            predicted_price = model.predict(future_dates)[0]
            future_amazon_price = round(predicted_price, 2)

        # Add result to Amazon predictions list
        amazon_predictions.append({
            "name": product["name"],
            "amazon_price": product["price"],
            "amazon_future_price": future_amazon_price,
            "image": product.get("image", ""),          # Add image
            "link": product.get("link", "#")            # Add link
        })

    # Process Flipkart products
    for product in flipkart_data:
        if product.get("price") is None:
            continue  # Skip if no price

        # Store current price in DB
        today = datetime.today()
        last_month = today - timedelta(days=30)
        collection.insert_one({
            "product_name": product["name"],
            "date": today,
            "price": product["price"],
            "platform": "Flipkart"
        })

        # Fetch past prices for this product (Flipkart only)
        prices_data = list(collection.find({
            "product_name": product["name"],
            "platform": "Flipkart",
            "date": {"$gte": last_month}
        }).sort("date", 1))

        future_flipkart_price = "No Data"
        if prices_data:
            # Prepare data
            dates = [(p["date"] - last_month).days for p in prices_data]
            prices = [p["price"] for p in prices_data]

            # Train model
            model = LinearRegression()
            X = np.array(dates).reshape(-1, 1)
            y = np.array(prices)
            model.fit(X, y)

            # Predict next price (3 days later)
            future_dates = np.array([[max(dates) + 3]])
            predicted_price = model.predict(future_dates)[0]
            future_flipkart_price = round(predicted_price, 2)

        # Add result to Flipkart predictions list
        flipkart_predictions.append({
            "name": product["name"],
            "flipkart_price": product["price"],
            "flipkart_future_price": future_flipkart_price,
            "image": product.get("image", ""),          # Add image
            "link": product.get("link", "#")            # Add link
        })

    # Return both Amazon and Flipkart predictions separately
    return amazon_predictions, flipkart_predictions

@app.route("/predict", methods=["GET", "POST"])
def price_prediction():
    if request.method == "POST":
        product_name = request.form.get("product", "").strip()

        if not product_name:
            return render_template("predict.html", error="Product name is required!")

        amazon_predictions, flipkart_predictions = predict_price(product_name)

        return render_template("predict.html", amazon_products=amazon_predictions, flipkart_products=flipkart_predictions)

    return render_template("predict.html", amazon_products=[], flipkart_products=[])

@app.route('/alerts', methods=['GET', 'POST'])
def alerts():
    if request.method == 'POST':
        email = request.form.get('email')
        product = request.form.get('product')
        platform = request.form.get('platform')
        
        # Safely get the 'desired_price' with default value if not provided
        desired_price = request.form.get('desired_price')
        
        if not desired_price:
            flash('Please enter a desired price.', 'danger')
            return redirect(url_for('alerts'))

        try:
            # Convert desired_price to float and then to integer
            desired_price = int(float(desired_price))
        except ValueError:
            flash('Invalid price format. Please enter a valid number.', 'danger')
            return redirect(url_for('alerts'))

        if platform == "Amazon":
            products = scrape_amazon(product)
        elif platform == "Flipkart":
            products = scrape_flipkart(product)
        else:
            products = []

        product_url = products[0].get("url") if products else "#"

        if product_url:
            if platform.lower() == "amazon" and product_url.startswith("/"):
                product_url = "https://www.amazon.in" + product_url
            elif platform.lower() == "flipkart" and product_url.startswith("/"):
                product_url = "https://www.flipkart.com" + product_url
            elif not product_url.startswith("http"):
                product_url = "https://" + product_url
            else:
                product_url = "#"


        alerts_collection.insert_one({
            "email": email,
            "product_name": product,
            "desired_price": desired_price,
            "platform": platform,
            "product_url": product_url
        })


        success = send_price_alert_email(email, product, desired_price, platform, product_url)
        if success:
            flash('Your alert was set successfully! A confirmation email has been sent. ✅')
        else:
            flash('Your alert was saved, but we couldn’t send a confirmation email. ❌')

        return redirect(url_for('alerts'))
    return render_template('alerts.html')


def get_current_price(product_name, platform):
    if platform == "Amazon":
        amazon_products = scrape_amazon(product_name, max_pages=5)
    elif platform == "Flipkart":
        flipkart_products = scrape_flipkart(product_name, max_pages=5)
    else:
        return None

    if not products:
        return None

    # Get the lowest price
    prices = [p["price"] for p in products if p["price"] is not None]
    if not prices:
        return None

    return {
        "price": min(prices),
        "product": product_name,
        "platform": platform
    }


def check_price_alerts():
    print("Checking price alerts...")
    try:
        alerts = alerts_collection.find()

        for alert in alerts:
            product_name = alert.get("product_name")
            desired_price = alert.get("desired_price")
            user_email = alert.get("email")
            platform = alert.get("platform")  # 'Amazon' or 'Flipkart'

            print(f"\nChecking for: {product_name} | Desired: {desired_price} | User: {user_email} | Platform: {platform}")

            current_price = None

            # Scrape price only from the selected platform
            if platform.lower() == "amazon":
                results = scrape_amazon(product_name)
            elif platform.lower() == "flipkart":
                results = scrape_flipkart(product_name)
            else:
                print(f"Unsupported platform: {platform}")
                continue

            # Find price of the best match (first result is usually most relevant)
            if results:
                try:
                    current_price = float(results[0].get("price", 0))
                    product_url = results[0].get("link")
                    print(f"Current price on {platform}: ₹{current_price}")
                except Exception as e:
                    print("Error parsing price:", e)
                    continue

                # If current price is less than or equal to desired price, send email
                if current_price <= desired_price:
                    send_email_notification(user_email, product_name, current_price, desired_price, platform, product_url)
                    alerts_collection.delete_one({"_id": alert["_id"]}) 
                else:
                    print("No price drop yet.")
            else:
                print(f"No results found on {platform} for '{product_name}'.")

    except Exception as e:
        print("Error checking alerts:", e)


def send_email_notification(to_email, product_name, current_price, desired_price, platform, product_url):
    print(f"Sending price drop email to {to_email} for {product_name}...")
    message = Mail(
        from_email=' # use your verified sender',  
        to_emails=to_email,
        subject=f'Price Drop Alert for {product_name}!',
        html_content=f"""
        <p>Hey there! 👋</p>
        <p>The price of <strong>{product_name}</strong> has dropped to ₹{current_price} on {platform}.</p>
        <p>Your alert was for ₹{desired_price}.</p>
        <p><a href="{product_url}" target="_blank">👉 Click here to view the product</a></p>
        <p>Cheers,<br>PriceDekho Team</p>
        """
    )

    try:
        sg = SendGridAPIClient('enter your sengridAPI with registered email')
        response = sg.send(message)
        print(f"Notification sent to {to_email}")
        return True
    except Exception as e:
        print(f"Error sending notification email: {e}")
        return False


def send_price_alert_email(user_email, product, price, platform, product_url):
    message = Mail(
        from_email=' # use your verified sender', 
        to_emails=user_email,
        subject='✅ Price Alert Set Successfully',
        html_content=f"""
        <h2>Hey there!</h2>
        <p>You’ve successfully set a price alert for:</p>
        <ul>
            <li><strong>Product:</strong> {product}</li>
            <li><strong>Platform:</strong> {platform}</li>
            <li><strong>Desired Price:</strong> ₹{price}</li>
        </ul>
        <p><a href="{product_url}" target="_blank">🔗 View Product on {platform}</a></p>
        <p>We’ll notify you as soon as the price drops below your desired amount.</p>
        <br>
        <p>Thanks for using <strong>Price Dekho</strong>! 🚀</p>
        """
    )

    try:
        sg = SendGridAPIClient(os.getenv('enter your sengridAPI with registered email'))
        response = sg.send(message)
        return response.status_code == 202
    except Exception as e:
        print("SendGrid Error:", e)
        return False

def start_scheduler():
    if not app.config['SCHEDULER_STARTED']:
        scheduler = BackgroundScheduler()
        scheduler.add_job(func=check_price_alerts, trigger="interval", minutes=1)
        scheduler.start()
        app.config['SCHEDULER_STARTED'] = True
        print("✅ Scheduler started only once.")



if __name__ == "__main__":
    start_scheduler()
    app.run(debug=True)

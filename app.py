from flask import Flask, request, jsonify
from pymongo import MongoClient
from twilio.rest import Client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import os

from flask_cors import CORS

# Load environment variables from the .env file
load_dotenv()

app = Flask(__name__)
CORS(app)  
# Twilio configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
GMAIL_USER = 'vibudeshrb.22cse@kongu.edu'
GMAIL_PASSWORD = 'andx xznk qhsn aagi'

# MongoDB configuration
mongo_client = MongoClient("mongodb+srv://vibudesh:040705@cluster0.oug8gz8.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = mongo_client['IOT']
collection = db['data']
collection2=db['pipe']
# Threshold value
THRESHOLD = 40

# Function to send SMS via Twilio
def send_sms(to_number, message_body):
    message = twilio_client.messages.create(
        body=message_body,
        from_=TWILIO_PHONE_NUMBER,
        to=to_number
    )
    return message.sid
# Function to send email
def send_email(to_email, subject, body):
    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, to_email, msg.as_string())

# Function to make a call via Twilio
def make_call(to_number, temperature, humidity, soil_moisture):
    url = f"http://127.0.0.1:5000/twiml?temperature={temperature}&humidity={humidity}&soilMoisture={soil_moisture}"
    call = twilio_client.calls.create(
        url=url,
        from_=TWILIO_PHONE_NUMBER,
        to=to_number
    )
    return call.sid
# API to store pipe status (on/off) from Flutter
@app.route('/send', methods=['POST'])
def store_pipe_status():
    data = request.get_json()
    pipe_status = data.get('pipeStatus')  # Expecting 'on' or 'off'
    to_number = '+919626513782'
    to_email = 'vibudesh0407@gmail.com'

    # Ensure only one document is stored in the collection
    # Delete the last document if any exists before inserting a new one
    collection2.delete_one({})  # Deletes the first document found in the collection

    # Store pipe status in MongoDB
    pipe_data = {
        "pipeStatus": pipe_status
    }
    collection2.insert_one(pipe_data)

    # Trigger alert or log depending on the pipe status
    if pipe_status == "on":
        message_body = "Pipe is now ON."
    elif pipe_status == "off":
        message_body = "Pipe is now OFF."
    else:
        return jsonify({"status": "Invalid pipe status"}), 400

    # Send SMS and Email for the pipe status change
    send_sms(to_number, message_body)
    send_email(to_email, "Pipe Status Update", message_body)

    return jsonify({"status": f"Pipe status '{pipe_status}' stored and alerts sent"})

# API to send data and trigger alert if threshold is exceeded
@app.route('/store', methods=['POST'])
def send():
    data = request.get_json()
    temp = data.get('temperature')
    humidity = data.get('humidity')
    soil_moisture = data.get('soilMoisture')
    to_number = '+919626513782'
    to_email = 'vibudesh0407@gmail.com'

    # Store data in MongoDB
    collection.insert_one(data)

    # Check if soil moisture is below threshold
    if soil_moisture < THRESHOLD:
        message_body = f"Alert! Soil moisture {soil_moisture}% is below the threshold of {THRESHOLD}%."

        # Send SMS
        sms_sid = send_sms(to_number, message_body)
        
        # Send Email
        send_email(to_email, "Threshold Alert", message_body)
        
        # Make a call
        call_sid = make_call(to_number, temp, humidity, soil_moisture)
        
        return jsonify({
            "status": "Alert triggered",
            "sms_sid": sms_sid,
            "call_sid": call_sid
        })

    return jsonify({"status": "Data stored without alert"})


# API to send data to MongoDB

@app.route('/')
def index():
    return jsonify({"message": "Welcome to the IoT Alert System"})

# API to receive the most recent data from MongoDB
@app.route('/receive', methods=['GET'])
def receive_data():
    # Retrieve the most recent document from MongoDB
    recent_record = collection.find_one(sort=[("_id", -1)])  # Sort by _id in descending order
    if recent_record:
        recent_record.pop('_id')  # Remove the MongoDB-specific "_id" field if present
    return jsonify(recent_record if recent_record else {"message": "No data found"})


# TwiML route to handle call
@app.route('/twiml', methods=['GET'])
def twiml():
    temperature = request.args.get('temperature')
    humidity = request.args.get('humidity')
    soil_moisture = request.args.get('soilMoisture')
    
    response = f"""<?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Say voice="alice">Alert! The soil moisture level is at {soil_moisture} percent, which is below the safe threshold.</Say>
        <Say voice="alice">Current temperature is {temperature} degrees Celsius and humidity is {humidity} percent.</Say>
    </Response>"""
    
    return response, 200, {'Content-Type': 'application/xml'}

if __name__ == '__main__':
   
    app.run(debug=True, host='0.0.0.0',  port = int(os.getenv("PORT", 5000)) )

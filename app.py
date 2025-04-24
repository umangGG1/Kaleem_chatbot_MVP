# app.py - Balanced resume builder application
from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
import os
from dotenv import load_dotenv
import pymongo
from langchain.chat_models import AzureChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
from langchain.prompts import PromptTemplate
from langchain.document_loaders import PyPDFLoader
import tempfile
from datetime import datetime
import uuid
import json

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)
app.secret_key = os.getenv("SECRET_KEY", "your-secret-key")

# MongoDB setup - simplified structure
mongo_client = pymongo.MongoClient(os.getenv("MONGODB_URI"))
db = mongo_client["resume_builder"]
users_collection = db["users"]

# Azure OpenAI setup
llm = AzureChatOpenAI(
    openai_api_version=os.getenv("OPENAI_API_VERSION"),
    deployment_name=os.getenv("AZURE_DEPLOYMENT"),
    openai_api_base=os.getenv("AZURE_ENDPOINT"),
    openai_api_key=os.getenv("AZURE_API_KEY"),
    temperature=0.7
)

# Define conversation prompt with personalization and follow-up capabilities
conversation_prompt = PromptTemplate(
    input_variables=["history", "input", "name"],
    template="""
    You are Kaleem, a friendly and helpful resume builder assistant. Your task is to collect information from users to help build their professional resume.
    
    Be conversational and friendly, addressing the user by their name: {name}
    Ask thoughtful follow-up questions (2 questions maximum) based on their responses to gather deeper insights.
    
    Focus on understanding:
    1. Their professional goals for the next 1-3 years
    2. What industries or roles they're targeting
    3. Their unique value proposition - what they want to be known for professionally
    4. Their key achievements with measurable results
    5. Their technical and soft skills that differentiate them
    
    Current conversation:
    {history}
    Human: {input}
    Kaleem:"""
)

# State management
STATES = {
    "GREETING": 0,
    "UPLOAD_RESUME": 1,
    "ASK_CONTACT_INFO": 2,  # First ask for any missing contact info
    "ASK_LINKEDIN": 3,      # Then ask for LinkedIn URL
    "ASK_GOALS": 4,         # Then career goals with follow-ups
    "ASK_VALUE_PROP": 5,    # Then value proposition with follow-ups
    "ASK_ACHIEVEMENTS": 6,  # Then achievements with follow-ups
    "ASK_EMAIL": 7,         # Finally ask for email
    "COMPLETE": 8
}

# Session data storage (temporary in-memory storage)
user_data = {}

# Helper functions
def extract_name_from_resume(resume_text):
    """Extract the user's name from their resume using the LLM"""
    extraction_prompt = f"""
    Extract only the full name of the person from this resume text. Return only the name, nothing else.
    
    Resume text:
    {resume_text[:2000]}
    
    Name:
    """
    response = llm.predict(extraction_prompt)
    return response.strip()

def extract_contact_info(resume_text):
    """Extract available contact information from resume"""
    extraction_prompt = f"""
    Extract available contact information from this resume text. Return a JSON with these keys:
    - email (if found)
    - phone (if found)
    - linkedin_url (if found)
    
    If any piece of information is not found, set its value to null.
    
    Resume text:
    {resume_text[:3000]}
    """
    response = llm.predict(extraction_prompt)
    
    # Try to parse as JSON, with fallback
    try:
        return json.loads(response)
    except:
        # In case parsing fails, return a default structure
        return {"email": None, "phone": None, "linkedin_url": None}

def is_contact_info_missing(contact_info):
    """Check if essential contact information is missing"""
    # Consider contact info missing if either email or phone is missing
    return contact_info.get("email") is None or contact_info.get("phone") is None

def generate_contact_info_question(user_name, contact_info):
    """Generate a personalized question about missing contact info"""
    missing = []
    if contact_info.get("email") is None:
        missing.append("email address")
    if contact_info.get("phone") is None:
        missing.append("phone number")
    
    missing_str = " and ".join(missing)
    return f"Thanks {user_name}! I couldn't find your {missing_str} in your resume. Your contact info is missing. Please provide your email and phone number below:"

def generate_linkedin_question(user_name):
    """Generate a personalized question about LinkedIn profile"""
    return f"Thank you, {user_name}. Could you please share your LinkedIn profile URL? This will help me understand your professional network and presence."

def generate_career_goals_question(user_name):
    """Generate a personalized question about career goals with follow-ups"""
    return f"Now, {user_name}, I'd like to understand your professional goals. What are you aiming to achieve in your career over the next 1-3 years? Which industries or roles are you targeting?"

def generate_value_prop_question(user_name):
    """Generate a personalized question about value proposition with follow-ups"""
    return f"Thank you for sharing that, {user_name}. What would you say is your unique value proposition or what do you want to be known for professionally? What sets you apart from others in your field?"

def generate_achievements_question(user_name):
    """Generate a personalized question about achievements with follow-ups"""
    return f"That's really helpful, {user_name}. Could you share 2-3 of your most significant professional achievements? If possible, include measurable results (e.g., increased revenue by 20%, led a team of 15, completed project under budget)."

def generate_follow_up_questions(topic, response):
    """Generate 2 follow-up questions based on a response about a topic"""
    prompt = f"""
    Based on this response about a person's {topic}:
    "{response}"
    
    Generate exactly 2 follow-up questions that would help gather deeper insights for building a professional resume.
    The questions should be conversational but focused on extracting valuable professional details.
    
    Return only the questions, numbered 1 and 2, without any additional text.
    """
    
    try:
        result = llm.predict(prompt)
        # Clean up and format the result
        lines = [line.strip() for line in result.split('\n') if line.strip()]
        # Filter out non-question lines and limit to 2 questions
        questions = [line.lstrip('0123456789. ') for line in lines if '?' in line][:2]
        
        if len(questions) == 2:
            return questions
        else:
            # Default questions if we couldn't generate proper follow-ups
            return [
                f"Could you elaborate more on your {topic}?",
                f"Is there anything else about your {topic} you'd like to share?"
            ]
    except Exception as e:
        print(f"Error generating follow-up questions: {str(e)}")
        return [
            f"Could you elaborate more on your {topic}?",
            f"Is there anything else about your {topic} you'd like to share?"
        ]

def calculate_completion_percentage(user_data_dict):
    """Calculate the percentage of information collected"""
    # Simplified calculation based on state
    state = user_data_dict.get("state", 0)
    
    state_percentages = {
        STATES["GREETING"]: 0,
        STATES["UPLOAD_RESUME"]: 10,
        STATES["ASK_CONTACT_INFO"]: 20,
        STATES["ASK_LINKEDIN"]: 30,
        STATES["ASK_GOALS"]: 50,
        STATES["ASK_VALUE_PROP"]: 65,
        STATES["ASK_ACHIEVEMENTS"]: 80,
        STATES["ASK_EMAIL"]: 90,
        STATES["COMPLETE"]: 100
    }
    
    return state_percentages.get(state, 0)

def store_chat_history(user_id, message, response):
    """Store chat history in the database"""
    users_collection.update_one(
        {"user_id": user_id},
        {"$push": {
            "chat_history": {
                "timestamp": datetime.now(),
                "user_message": message,
                "assistant_response": response
            }
        }},
        upsert=True
    )

def update_user_data(user_id, data):
    """Update user data in MongoDB"""
    users_collection.update_one(
        {"user_id": user_id},
        {"$set": data},
        upsert=True
    )

# Routes
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    user_id = data.get("user_id")
    message = data.get("message")
    
    # Initialize user data if not exists
    if user_id not in user_data:
        user_data[user_id] = {
            "state": STATES["GREETING"],
            "name": "",
            "resume_text": "",
            "contact_info": {},
            "linkedin_url": "",
            "professional_goals": "",
            "value_proposition": "",
            "achievements": "",
            "email": "",
            "follow_up_count": 0
        }
    
    state = user_data[user_id]["state"]
    user_name = user_data[user_id].get("name", "")
    follow_up_count = user_data[user_id].get("follow_up_count", 0)
    
    # Initialize conversation if not already done
    if "conversation" not in user_data[user_id]:
        user_data[user_id]["conversation"] = ConversationChain(
            llm=llm,
            memory=ConversationBufferMemory(return_messages=True),
            prompt=conversation_prompt.partial(name=user_name),
            verbose=True
        )
    
    # Handle different states
    response = ""
    
    if state == STATES["GREETING"]:
        user_data[user_id]["state"] = STATES["UPLOAD_RESUME"]
        response = "Hello! I'm Kaleem, your resume building assistant. To get started, please upload your current resume so I can analyze it and help you improve it."
    
    elif state == STATES["UPLOAD_RESUME"]:
        # Handle case where user sends message instead of uploading resume
        name_mention = f", {user_name}" if user_name else ""
        response = f"I need your resume to proceed{name_mention}. Please use the upload button to share your resume in PDF format."
    
    elif state == STATES["ASK_CONTACT_INFO"]:
        # Store contact info response
        contact_parts = message.strip().split("\n")
        if len(contact_parts) >= 1:
            # Try to extract email
            for part in contact_parts:
                if "@" in part and "." in part:
                    user_data[user_id]["contact_info"]["email"] = part.strip()
                elif any(char.isdigit() for char in part) and len(part.strip()) >= 7:
                    user_data[user_id]["contact_info"]["phone"] = part.strip()
        
        # Move to LinkedIn question
        user_data[user_id]["state"] = STATES["ASK_LINKEDIN"]
        response = generate_linkedin_question(user_name)
    
    elif state == STATES["ASK_LINKEDIN"]:
        # Store LinkedIn URL
        user_data[user_id]["linkedin_url"] = message.strip()
        
        # Update database
        update_user_data(user_id, {
            "linkedin_url": message.strip(),
            "updated_at": datetime.now()
        })
        
        # Move to goals question
        user_data[user_id]["state"] = STATES["ASK_GOALS"]
        user_data[user_id]["follow_up_count"] = 0
        response = generate_career_goals_question(user_name)
    
    elif state == STATES["ASK_GOALS"]:
        # Store goals response or handle follow-up
        if follow_up_count == 0:
            # First response - store main goals
            user_data[user_id]["professional_goals"] = message
            
            # Generate follow-up questions
            follow_up_questions = generate_follow_up_questions("career goals", message)
            user_data[user_id]["follow_up_count"] = 1
            
            response = f"Thank you for sharing that, {user_name}. {follow_up_questions[0]}"
        
        elif follow_up_count == 1:
            # Second response - store follow-up and ask second follow-up
            user_data[user_id]["professional_goals_followup1"] = message
            
            # Get stored follow-up questions
            follow_up_questions = generate_follow_up_questions("career goals", user_data[user_id]["professional_goals"])
            user_data[user_id]["follow_up_count"] = 2
            
            response = f"I appreciate that insight, {user_name}. One more question about your career goals: {follow_up_questions[1]}"
        
        else:
            # Third response - store follow-up and move to value proposition
            user_data[user_id]["professional_goals_followup2"] = message
            
            # Update database
            update_user_data(user_id, {
                "professional_goals": user_data[user_id]["professional_goals"],
                "professional_goals_followups": [
                    user_data[user_id].get("professional_goals_followup1", ""),
                    user_data[user_id].get("professional_goals_followup2", "")
                ],
                "updated_at": datetime.now()
            })
            
            # Move to value proposition
            user_data[user_id]["state"] = STATES["ASK_VALUE_PROP"]
            user_data[user_id]["follow_up_count"] = 0
            
            response = generate_value_prop_question(user_name)
    
    elif state == STATES["ASK_VALUE_PROP"]:
        # Store value proposition response or handle follow-up
        if follow_up_count == 0:
            # First response - store main value proposition
            user_data[user_id]["value_proposition"] = message
            
            # Generate follow-up questions
            follow_up_questions = generate_follow_up_questions("value proposition", message)
            user_data[user_id]["follow_up_count"] = 1
            
            response = f"That's a compelling value proposition, {user_name}. {follow_up_questions[0]}"
        
        elif follow_up_count == 1:
            # Second response - store follow-up and ask second follow-up
            user_data[user_id]["value_proposition_followup1"] = message
            
            # Get stored follow-up questions
            follow_up_questions = generate_follow_up_questions("value proposition", user_data[user_id]["value_proposition"])
            user_data[user_id]["follow_up_count"] = 2
            
            response = f"Excellent point, {user_name}. One more question about your unique strengths: {follow_up_questions[1]}"
        
        else:
            # Third response - store follow-up and move to achievements
            user_data[user_id]["value_proposition_followup2"] = message
            
            # Update database
            update_user_data(user_id, {
                "value_proposition": user_data[user_id]["value_proposition"],
                "value_proposition_followups": [
                    user_data[user_id].get("value_proposition_followup1", ""),
                    user_data[user_id].get("value_proposition_followup2", "")
                ],
                "updated_at": datetime.now()
            })
            
            # Move to achievements
            user_data[user_id]["state"] = STATES["ASK_ACHIEVEMENTS"]
            user_data[user_id]["follow_up_count"] = 0
            
            response = generate_achievements_question(user_name)
    
    elif state == STATES["ASK_ACHIEVEMENTS"]:
        # Store achievements response or handle follow-up
        if follow_up_count == 0:
            # First response - store main achievements
            user_data[user_id]["achievements"] = message
            
            # Generate follow-up questions
            follow_up_questions = generate_follow_up_questions("achievements", message)
            user_data[user_id]["follow_up_count"] = 1
            
            response = f"Those are impressive achievements, {user_name}. {follow_up_questions[0]}"
        
        elif follow_up_count == 1:
            # Second response - store follow-up and ask second follow-up
            user_data[user_id]["achievements_followup1"] = message
            
            # Get stored follow-up questions
            follow_up_questions = generate_follow_up_questions("achievements", user_data[user_id]["achievements"])
            user_data[user_id]["follow_up_count"] = 2
            
            response = f"Thank you for elaborating, {user_name}. One last question about your accomplishments: {follow_up_questions[1]}"
        
        else:
            # Third response - store follow-up and move to email
            user_data[user_id]["achievements_followup2"] = message
            
            # Update database
            update_user_data(user_id, {
                "achievements": user_data[user_id]["achievements"],
                "achievements_followups": [
                    user_data[user_id].get("achievements_followup1", ""),
                    user_data[user_id].get("achievements_followup2", "")
                ],
                "updated_at": datetime.now()
            })
            
            # Move to email
            user_data[user_id]["state"] = STATES["ASK_EMAIL"]
            
            response = f"Thank you for sharing those detailed achievements, {user_name}! Just one final question - what email address should I send your completed resume to?"
    
    elif state == STATES["ASK_EMAIL"]:
        # Process email response
        user_data[user_id]["email"] = message
        user_data[user_id]["state"] = STATES["COMPLETE"]
        
        # Update database with completed status
        update_user_data(user_id, {
            "email": message,
            "status": "information_collected",
            "updated_at": datetime.now()
        })
        
        response = f"Perfect, {user_name}! I've collected all the necessary information to build your professional resume. You'll receive your completed resume at {message} within 24-48 hours. Thank you for using our service!"
    
    elif state == STATES["COMPLETE"]:
        # Handle general chat/questions when in COMPLETE state
        response = user_data[user_id]["conversation"].predict(
            input=message, 
            name=user_name
        )
    
    else:
        # Default response using conversation chain
        response = user_data[user_id]["conversation"].predict(
            input=message, 
            name=user_name
        )
    
    # Calculate completion percentage
    completion_percentage = calculate_completion_percentage(user_data[user_id])
    
    # Store chat in history
    store_chat_history(user_id, message, response)
    
    return jsonify({
        "response": response,
        "completion_percentage": completion_percentage
    })

@app.route("/api/upload-resume", methods=["POST"])
def upload_resume():
    """Handle file upload for resume"""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    user_id = request.form.get('user_id')
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file and file.filename.endswith('.pdf'):
        # Create temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            file.save(temp_file.name)
            temp_path = temp_file.name
        
        try:
            # Process PDF
            loader = PyPDFLoader(temp_path)
            pages = loader.load()
            resume_text = "\n".join([page.page_content for page in pages])
            
            # Extract name from resume
            name = extract_name_from_resume(resume_text)
            
            # Extract contact information
            contact_info = extract_contact_info(resume_text)
            
            # Initialize user data if not exists
            if user_id not in user_data:
                user_data[user_id] = {
                    "state": STATES["UPLOAD_RESUME"],
                    "user_id": user_id
                }
            
            # Update user data with resume information
            user_data[user_id].update({
                "resume_text": resume_text,
                "name": name,
                "contact_info": contact_info,
                "follow_up_count": 0
            })
            
            # Create personalized conversation
            user_data[user_id]["conversation"] = ConversationChain(
                llm=llm,
                memory=ConversationBufferMemory(return_messages=True),
                prompt=conversation_prompt.partial(name=name),
                verbose=True
            )
            
            # Store in database - simplified with just 3 key items
            update_user_data(user_id, {
                "user_id": user_id,
                "resume_text": resume_text,
                "linkedin_url": contact_info.get("linkedin_url", ""),
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            })
            
            # Clean up temp file
            os.unlink(temp_path)
            
            # Determine next state and response
            response_text = f"Thanks for uploading your resume, {name}! "
            
            # Check if contact info is missing
            if is_contact_info_missing(contact_info):
                user_data[user_id]["state"] = STATES["ASK_CONTACT_INFO"]
                response_text += generate_contact_info_question(name, contact_info).lstrip(f"Thanks {name}! ")
            else:
                # If contact info is complete, go to LinkedIn
                user_data[user_id]["state"] = STATES["ASK_LINKEDIN"]
                response_text += generate_linkedin_question(name).lstrip(f"Thank you, {name}. ")
            
            # Calculate completion percentage
            completion_percentage = calculate_completion_percentage(user_data[user_id])
            
            return jsonify({
                "success": True,
                "name": name,
                "response": response_text,
                "completion_percentage": completion_percentage
            })
            
        except Exception as e:
            # Clean up temp file in case of error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            print(f"Error processing PDF: {str(e)}")
            return jsonify({"error": f"Error processing your PDF: {str(e)}"}), 500
    
    return jsonify({"error": "Invalid file format. Please upload a PDF."}), 400

@app.route("/", methods=["GET"])
def index():
    """Serve the main HTML page"""
    return send_from_directory('.', 'static/index.html')

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@app.route("/api/submit-contact", methods=["POST"])
def submit_contact():
    """Handle contact information submission"""
    try:
        # Get JSON data from the request
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400

        user_id = data.get("user_id")
        email = data.get("email")
        phone = data.get("phone")

        # Validate inputs
        if not user_id or not email or not phone:
            return jsonify({"error": "Missing required fields: user_id, email, or phone"}), 400

        # Validate email format
        import re
        email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_regex, email):
            return jsonify({"error": "Invalid email format"}), 400

        # Validate phone format (align with frontend regex)
        phone_regex = r'^[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4}$'
        if not re.match(phone_regex, phone):
            return jsonify({"error": "Invalid phone format"}), 400

        # Check if user exists
        if user_id not in user_data:
            return jsonify({"error": "User not found"}), 404

        # Update user data with contact information
        user_data[user_id]["contact_info"]["email"] = email
        user_data[user_id]["contact_info"]["phone"] = phone

        # Update database
        update_user_data(user_id, {
            "contact_info": {
                "email": email,
                "phone": phone
            },
            "updated_at": datetime.now()
        })

        # Move to LinkedIn question
        user_data[user_id]["state"] = STATES["ASK_LINKEDIN"]
        response = generate_linkedin_question(user_data[user_id].get("name", ""))

        # Calculate completion percentage
        completion_percentage = calculate_completion_percentage(user_data[user_id])

        # Store chat in history (construct message to match frontend)
        message = f"Email: {email}\nPhone: {phone}"
        store_chat_history(user_id, message, response)

        return jsonify({
            "response": response,
            "completion_percentage": completion_percentage
        })

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
if __name__ == "__main__":
    # Ensure static folder exists
    if not os.path.exists('static'):
        os.makedirs('static')
    
    # Initialize the app
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
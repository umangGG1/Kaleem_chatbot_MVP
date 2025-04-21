# Resume Builder Chatbot

A conversational AI assistant that helps users build professional resumes through an interactive chat interface.

## Features

- **Intelligent Resume Analysis**: Automatically extracts information from uploaded resumes
- **Personalized Conversations**: Addresses users by name and adapts to their responses
- **Structured Information Collection**: Gathers essential career details through guided questions
- **Follow-up Questions**: Asks targeted follow-up questions to extract deeper insights
- **Visual Progress Tracking**: Shows completion percentage throughout the process
- **Professional UI**: Clean, modern interface with intuitive file upload

## Architecture

### Backend (Flask + Azure OpenAI)
- Flask web server handling API requests
- Azure OpenAI for natural language processing and conversation
- MongoDB for data storage and retrieval
- PDF processing for resume extraction

### Frontend (HTML/CSS/JavaScript)
- Responsive web interface with Bootstrap
- Real-time chat functionality
- Progress indicator
- Drag-and-drop file upload

## Setup Instructions

### Prerequisites
- Python 3.8+
- MongoDB
- Azure OpenAI API access

### Environment Setup

1. Clone the repository
   ```bash
   git clone https://github.com/yourusername/resume-builder.git
   cd resume-builder
   ```

2. Create a virtual environment
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file with the following variables:
   ```
   MONGODB_URI=your_mongodb_connection_string
   OPENAI_API_VERSION=your_openai_api_version
   AZURE_DEPLOYMENT=your_azure_deployment_name
   AZURE_ENDPOINT=your_azure_endpoint
   AZURE_API_KEY=your_azure_api_key
   SECRET_KEY=your_flask_secret_key
   ```

### Running the Application

1. Start the Flask server
   ```bash
   python app.py
   ```

2. Access the application at http://localhost:5000

## Project Structure

```
resume-builder/
├── app.py                  # Main Flask application
├── static/                 # Static assets
│   ├── index.html          # Main frontend HTML
│   ├── css/                # Stylesheets
│   └── js/                 # JavaScript files
├── templates/              # Flask templates (if used)
├── .env                    # Environment variables (not tracked in git)
├── .gitignore              # Git ignore file
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

## Usage

1. **Start**: The chatbot welcomes you and asks for your resume
2. **Upload Resume**: Upload your current resume in PDF format
3. **Basic Information**: Provide any missing contact details and LinkedIn URL
4. **Career Goals**: Share your professional goals with follow-up questions
5. **Value Proposition**: Describe what makes you unique professionally
6. **Achievements**: List your key professional accomplishments
7. **Email**: Provide your email for resume delivery
8. **Complete**: Receive confirmation that your resume will be prepared

## Data Storage

The application stores three key pieces of information:
1. **Resume Text**: Extracted from the uploaded PDF
2. **LinkedIn URL**: Provided by the user
3. **Chat History**: Complete conversation for context and reference

## Dependencies

- Flask: Web framework
- Flask-CORS: Cross-origin resource sharing
- PyMongo: MongoDB integration
- LangChain: LLM framework
- python-dotenv: Environment variable management
- PyPDFLoader: PDF processing

## Security Considerations

- The application uses environment variables for sensitive credentials
- User data is stored securely in MongoDB
- File uploads are validated and processed securely

## Future Enhancements

- Integration with LinkedIn API for profile import
- Resume template selection
- Direct document generation and download
- Skill assessment and recommendation
- Industry-specific resume advice

## License

[MIT License](LICENSE)

## Contributors

- Umang Singh

## Acknowledgments

- This project utilizes Azure OpenAI's powerful language models
- Interface design inspired by modern chat applications
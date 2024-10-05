# CompCheckGenerator

## Prerequisites

- Python 3.9 or higher

## Installation

1. Clone the repository:
   ```
   git clone <repository_url>
   ```
   Replace `<repository_url>` with the actual URL of the project repository.

2. Navigate to the project directory:
   ```
   cd CompCheckGenerator
   ```

3. Create a virtual environment (optional but recommended):
   ```
   python -m venv venv
   ```

4. Activate the virtual environment:
   - On Windows:
     ```
     venv\Scripts\activate
     ```
   - On macOS and Linux:
     ```
     source venv/bin/activate
     ```

5. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Configuration

1. Set up the environment variables:
   Create a `.env` file in the project root directory and add your OpenAI API key:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

## Running the Application

To run the Flask application:
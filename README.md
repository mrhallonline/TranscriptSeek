# TranscriptSeek

TranscriptSeek is a tool designed to enhance qualitative research by allowing users to search through transcribed video and audio files. Using natural language processing (NLP) techniques, TranscriptSeek enables researchers to locate specific terms or phrases within transcripts and directly jump to the corresponding timestamps in the media files. This feature is particularly useful for researchers who need to analyze detailed discussions and interviews efficiently.

## Features

- **Transcription Search**: Search for keywords or phrases within transcriptions.
- **Timestamp Navigation**: Jump directly to the relevant part of the video or audio file from the search results.
- **Media Management**: Organize and manage multiple media files and their corresponding transcriptions.
- **User-Friendly Interface**: Simple and intuitive interface designed for ease of use in research settings.

## Getting Started

### Prerequisites

- PostgreSQL
- Python 3.8+
- Pandas, SQLAlchemy

### Installation


Set up a Python virtual environment and activate it:

```bash
Copy code
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`

Install the required Python packages:

bash
Copy code
pip install -r requirements.txt
Initialize the database:

Ensure PostgreSQL is running.
Create a database named TranscriptSeek.
Run the SQL scripts found in the sql/ directory to set up the tables.
Configuration
Modify the config.py file to include your database credentials and other configurations.
Usage
To start the application, run:

bash
Copy code
python app.py
Navigate to http://localhost:5000 to access the web interface. Use the search bar to query terms in your transcripts, and click on results to view them in the media player.

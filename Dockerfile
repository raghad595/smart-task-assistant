# Use official Python runtime as a parent image
FROM python:3.11-slim

# Copy the requirements file for caching purposes
COPY requirements.txt .

# Install required Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# define the port the app runs on
EXPOSE 8000

# Command to run the application
# We use a shell command to initialize the DB first, then start Uvicorn
CMD ["sh", "-c", "python init_db.py && uvicorn main:app --host 0.0.0.0 --port 8000"]
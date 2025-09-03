# Web Application

This directory contains a Flask web application that serves several HTML pages.

## Running the Application

1.  **Install dependencies:**
    Make sure you have Python and pip installed. Then, install the required packages using the following command:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Set ngrok authtoken:**
    To use ngrok, you need to have an authtoken. You can get one from the [ngrok dashboard](https://dashboard.ngrok.com/get-started/your-authtoken).
    Once you have your authtoken, set it as an environment variable:
    ```bash
    export NGROK_AUTHTOKEN="YOUR_AUTHTOKEN"
    ```
    Replace `"YOUR_AUTHTOKEN"` with your actual ngrok authtoken.

3.  **Run the Flask application:**
    ```bash
    python app.py
    ```
    The application will start, and you will see an ngrok URL in the console. You can use this URL to access the web application from anywhere.

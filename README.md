# MediMate

A local medication-management prototype for reviewing medicine schedules, interactions and adherence. Works on Windows and macOS.

## Instructions to run

1. Install Python 3.10 or newer from [python.org/downloads](https://www.python.org/downloads/) if it is not already installed. 
2. Download MediMate.On this GitHub page, click **Code → Download ZIP**. Open the downloaded ZIP and extract the folder.
3. Start the application.
   - **Windows:** Open the extracted folder, right-click an empty area and choose **Open in Terminal**. Paste the following command and press Enter:
     ```powershell
     py -3 -B start_windows.py
     ```
   - **Mac:** Open **Terminal**. Type `cd ` (including the space), drag the extracted MediMate folder into the Terminal window, and press Enter. Then paste:
     ```bash
     python3 -B start_review.py
     ```
4. Open MediMate. Your browser should open automatically. Otherwise, enter [http://127.0.0.1:8742](http://127.0.0.1:8742) in your browser. Keep the Terminal window open while using the application.
5. Try the features. Add fictional medicines, set their scheduled times, check interactions, review the adherence calendar and switch between family profiles.
6. Enable reminders (optional). Go to Settings → Set up background reminders, confirm the prompt and allow notifications on your computer. The reminder helper is already included. Notifications can repeat every 15 minutes until a dose is marked taken. Use Test notification in Settings to check browser alerts. Background alerts require the computer to be awake and signed in.

Both medication reference databases are included. There is nothing else to download for interaction checking. Medication Q&A is currently non-functional as I have not included the OpenAI API key in this test prototype. To stop the application, return to Terminal and press Ctrl+C. If background reminders were enabled, turn them off in Settings separately.

"A large language model (LLM) agent that searches for a question on the web and navigates through links to gather information."

The last code is the SON/main.py,

Broke but better code is Websocket/main.py,

in terminal can be runned by uvicorn main:app --reload --host 0.0.0.0 --port 8004 and open the html file

and env file contains this:

AWS_ACCESS_KEY_ID=...

AWS_SECRET_ACCESS_KEY=...

GOOGLE_API_KEY=...

LLM=...(Claude or Gemini)

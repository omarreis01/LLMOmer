from fastapi import FastAPI, WebSocket
from configuration.config import get_model
from connection_manager import ConnectionManager
from search_logic import search_for_answer
import json

app = FastAPI()
manager = ConnectionManager()
model = get_model()


#Abstrac class ya da protocol class ----OKEY
#birkaç fileda yaz,birbirinden çek, klasörlerde de ayrı böl ----OKEY
#pydantic modeller uzerinde yap,  promptları dümdüz verme object olarak ver-


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            url = message.get("url")
            question = message.get("question")

            # Use the search_for_answer function to find the response
            answer, link = await search_for_answer(websocket, model, url, question, "detailed")

            if answer is None:
                answer = "No relevant information is found"
                link = "No link"

            # Send response back to the client
            response_data = json.dumps({
                "question": question,
                "answer": answer,
                "link": link
            }, ensure_ascii=False, indent=4)

            await manager.send_personal_message(response_data, websocket)
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast("Client disconnected")

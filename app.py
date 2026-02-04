from flask import Flask, request
import requests
import os
import base64
from openai import OpenAI

app = Flask(__name__)

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

print(f"PHONE_NUMBER_ID: {PHONE_NUMBER_ID}")
print(f"WHATSAPP_TOKEN exists: {bool(WHATSAPP_TOKEN)}")
print(f"OPENAI_API_KEY exists: {bool(OPENAI_API_KEY)}")

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """Eres Sonia, una asistente personal para una persona mayor.
Tono y estilo:
- Educada, amable y clara, con un punto de alegria tranquila.
- No haces chistes ni bromas salvo que te los pidan.
- Respondes en espanol por defecto. Si el usuario pide otro idioma, te adaptas.
- Respuestas concisas y precisas. Si el usuario quiere mas detalle, amplias.
Comportamiento:
- Actuas como asistente: ayudas a resolver tareas, dudas y organizacion diaria.
- Si falta informacion para responder bien, haces 1 o 2 preguntas concretas.
- No inventas datos. Si no sabes algo, lo dices y propones una alternativa.
Primera interaccion:
- Si es el primer mensaje de la conversacion, saluda y presentate: Hola, soy Sonia, tu asistente personal. Estoy aqui para ayudarte con lo que necesites.
Seguridad y limites:
- Nunca usas palabrotas ni lenguaje ofensivo.
- Rechazas solicitudes sexuales, explicitas, humillantes, violentas, ilegales o peligrosas.
- Si te piden ese tipo de cosas, respondes con una negativa breve y ofreces ayuda con algo seguro y util.
- Si detectas que el usuario puede estar en riesgo, respondes con calma, recomiendas pedir ayuda inmediata a una persona de confianza o a servicios de emergencia locales, y ofreces apoyo con pasos seguros."""


def download_whatsapp_media(media_id):
    url_response = requests.get(
        f"https://graph.facebook.com/v18.0/{media_id}",
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    )
    media_url = url_response.json().get("url")
    
    if not media_url:
        print(f"Could not get media URL: {url_response.text}")
        return None
    
    media_response = requests.get(
        media_url,
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    )
    
    if media_response.status_code == 200:
        return base64.b64encode(media_response.content).decode("utf-8")
    else:
        print(f"Could not download media: {media_response.status_code}")
        return None


def send_whatsapp_message(to, text):
    response = requests.post(
        f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages",
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"},
        json={
            "messaging_product": "whatsapp",
            "to": to,
            "text": {"body": text}
        }
    )
    print(f"WhatsApp API response: {response.status_code} - {response.text}")
    return response


@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    
    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook verified!")
        return challenge, 200
    return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    print("Received:", data)
    
    try:
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        
        print(f"Messages found: {len(messages)}")
        
        if messages:
            msg = messages[0]
            sender = msg["from"]
            msg_type = msg.get("type")
            
            print(f"Sender: {sender}, Type: {msg_type}")
            
            user_content = []
            
            if msg_type == "text":
                text = msg.get("text", {}).get("body", "")
                print(f"Text: {text}")
                if text:
                    user_content.append({"type": "text", "text": text})
            
            elif msg_type == "image":
                image_data = msg.get("image", {})
                media_id = image_data.get("id")
                caption = image_data.get("caption", "")
                
                print(f"Image received, media_id: {media_id}, caption: {caption}")
                
                image_base64 = download_whatsapp_media(media_id)
                
                if image_base64:
                    user_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    })
                    if caption:
                        user_content.append({"type": "text", "text": caption})
                    else:
                        user_content.append({"type": "text", "text": "Que ves en esta imagen?"})
                else:
                    user_content.append({"type": "text", "text": "El usuario envio una imagen pero no pude descargarla."})
            
            else:
                print(f"Unsupported message type: {msg_type}")
                send_whatsapp_message(sender, "Lo siento, solo puedo procesar mensajes de texto e imagenes por ahora.")
                return "OK", 200
            
            if user_content:
                print("Calling OpenAI...")
                response = client.chat.completions.create(
                    model="gpt-4.1-nano",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_content}
                    ]
                )
                reply_text = response.choices[0].message.content
                print(f"OpenAI reply: {reply_text}")
                
                send_whatsapp_message(sender, reply_text)
                
    except Exception as e:
        print(f"Error: {e}")
    
    return "OK", 200


@app.route("/", methods=["GET"])
def home():
    return "WhatsApp Bot is running!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

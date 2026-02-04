from flask import Flask, request
import requests
import os
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")

SYSTEM_PROMPT = """Eres Sonia, una asistente personal para una persona mayor.
Tono y estilo:
- Educada, amable y clara, con un punto de alegría tranquila.
- No haces chistes ni bromas salvo que te los pidan.
- Respondes en español por defecto. Si el usuario pide otro idioma, te adaptas.
- Respuestas concisas y precisas. Si el usuario quiere más detalle, amplías.
Comportamiento:
- Actúas como asistente: ayudas a resolver tareas, dudas y organización diaria.
- Si falta información para responder bien, haces 1 o 2 preguntas concretas.
- No inventas datos. Si no sabes algo, lo dices y propones una alternativa.
Primera interacción:
- Si es el primer mensaje de la conversación, saluda y preséntate: "Hola, soy Sonia, tu asistente personal. Estoy aquí para ayudarte con lo que necesites."
Seguridad y límites:
- Nunca usas palabrotas ni lenguaje ofensivo.
- Rechazas solicitudes sexuales, explícitas, humillantes, violentas, ilegales o peligrosas.
- Si te piden ese tipo de cosas, respondes con una negativa breve y ofreces ayuda con algo seguro y útil.
- Si detectas que el usuario puede estar en riesgo (por ejemplo, autolesión), respondes con calma, recomiendas pedir ayuda inmediata a una persona de confianza o a servicios de emergencia locales, y ofreces apoyo con pasos seguros."""

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
        
        if messages:
            msg = messages[0]
            sender = msg["from"]
            text = msg.get("text", {}).get("body", "")
            
            if text:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": text}
                    ]
                )
                reply_text = response.choices[0].message.content
                
                requests.post(
                    f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages",
                    headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"},
                    json={
                        "messaging_product": "whatsapp",
                        "to": sender,
                        "text": {"body": reply_text}
                    }
                )
    except Exception as e:
        print(f"Error: {e}")
    
    return "OK", 200

@app.route("/", methods=["GET"])
def home():
    return "WhatsApp Bot is running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

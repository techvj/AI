import os
import json
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def create_servicenow_incident(short_description, description):
    print(f"Creating incident with short description: {short_description} and description: {description}")
    return {"status": "Incident created", "short_description": short_description, "description": description}

def request_servicenow_item(item_name, quantity):
    print(f"Requesting item: {item_name}, quantity: {quantity}")
    return {"status": "Item requested", "item_name": item_name, "quantity": quantity}

def add_comment_to_servicenow_ticket(ticket_number, comment):
    print(f"Adding comment to ticket: {ticket_number}, comment: {comment}")
    return {"status": "Comment added", "ticket_number": ticket_number, "comment": comment}

functions = [
    {
        "name": "create_servicenow_incident",
        "description": "Creates a new incident in ServiceNow.",
        "parameters": {
            "type": "object",
            "properties": {
                "short_description": {
                    "type": "string",
                    "description": "Short description of the incident.",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description of the incident.",
                },
            },
            "required": ["short_description", "description"],
        },
    },
    {
        "name": "request_servicenow_item",
        "description": "Requests an item from the ServiceNow service catalog.",
        "parameters": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "Name of the item to request.",
                },
                "quantity": {
                    "type": "integer",
                    "description": "Quantity of the item to request.",
                },
            },
            "required": ["item_name", "quantity"],
        },
    },
    {
        "name": "add_comment_to_servicenow_ticket",
        "description": "Adds a comment to an existing ticket in ServiceNow.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticket_number": {
                    "type": "string",
                    "description": "Number of the ticket to add a comment to.",
                },
                "comment": {
                    "type": "string",
                    "description": "Comment to add to the ticket.",
                },
            },
            "required": ["ticket_number", "comment"],
        },
    },
]

@app.route('/api/v1/message', methods=['POST'])
def servicenow_interact():
    try:
        data = request.get_json()
        user_message = data.get("message")

        if not user_message:
            return jsonify({"error": "Message is required"}), 400

        response = client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that interacts with Service Now. Please use the appropriate functions to answer the user requests."},
                {"role": "user", "content": user_message},
            ],
            functions=functions,
            function_call="auto",
        )

        response_message = response.choices[0].message
        if response_message.function_call:
            function_name = response_message.function_call.name
            function_args = json.loads(response_message.function_call.arguments)

            if function_name == "create_servicenow_incident":
                function_response = create_servicenow_incident(**function_args)
            elif function_name == "request_servicenow_item":
                function_response = request_servicenow_item(**function_args)
            elif function_name == "add_comment_to_servicenow_ticket":
                function_response = add_comment_to_servicenow_ticket(**function_args)
            else:
                return jsonify({"error": "Function not found"}), 500
            return jsonify(function_response)
        else:
           return jsonify({"response": response_message.content})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
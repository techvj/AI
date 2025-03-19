from flask import Flask, request, jsonify
import os
import autogen

app = Flask(__name__)

os.environ['OLLAMA_BASE_URL'] = 'http://localhost:11434/v1'

config_list = autogen.config_list_from_models(model_list=["mistral"], filter_dict={"model": {"mistral": {"max_tokens": 1024}}})
llm_config = {
    "config_list": config_list,
    "cache_seed": 42,
    "model": "mistral",
    "base_url": os.environ['OLLAMA_BASE_URL'],
}

def create_servicenow_incident(short_description, description):
    instance_name = os.environ.get("SERVICENOW_HOST")
    user = os.environ.get("SERVICENOW_USER")
    password = os.environ.get("SERVICENOW_PASSWORD")
    import requests
    import json
    url = f"https://{instance_name}.service-now.com/api/now/table/incident"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    auth = (user, password)
    payload = {
        "short_description": short_description,
        "description": description,
    }
    try:
        response = requests.post(url, headers=headers, auth=auth, data=json.dumps(payload))
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error creating incident: {e}")
        return None

def request_servicenow_item(item_name, quantity=1):
    instance_name = os.environ.get("SERVICENOW_HOST")
    user = os.environ.get("SERVICENOW_USER")
    password = os.environ.get("SERVICENOW_PASSWORD")
    import requests
    import json
    url = f"https://{instance_name}.service-now.com/api/sn_sc/servicecatalog/items"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    auth = (user, password)

    try:
        response = requests.get(url, headers=headers, auth=auth)
        response.raise_for_status()
        items = response.json().get('result', [])

        item_sys_id = None
        for item in items:
            if item.get('name') == item_name:
                item_sys_id = item.get('sys_id')
                break

        if not item_sys_id:
            print(f"Item '{item_name}' not found.")
            return None

        request_url = f"https://{instance_name}.service-now.com/api/sn_sc/servicecatalog/items/{item_sys_id}/order_now"
        request_payload = {"quantity": quantity}
        request_response = requests.post(request_url, headers=headers, auth=auth, data=json.dumps(request_payload))
        request_response.raise_for_status()
        return request_response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error requesting item: {e}")
        return None

def add_comment_to_servicenow_ticket(ticket_number, comment):
    instance_name = os.environ.get("SERVICENOW_HOST")
    user = os.environ.get("SERVICENOW_USER")
    password = os.environ.get("SERVICENOW_PASSWORD")
    import requests
    import json
    url = f"https://{instance_name}.service-now.com/api/now/table/incident"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    auth = (user, password)
    try:
        get_response = requests.get(f"{url}?sysparm_query=number={ticket_number}", headers=headers, auth=auth)
        get_response.raise_for_status()
        incident = get_response.json()['result'][0]
        sys_id = incident['sys_id']
        comment_url = f"{url}/{sys_id}"

        payload = {"comments": comment}
        comment_response = requests.put(comment_url, headers=headers, auth=auth, data=json.dumps(payload))
        comment_response.raise_for_status()
        return comment_response.json()

    except requests.exceptions.RequestException as e:
        print(f"Error adding comment to ticket: {e}")
        return None
    except IndexError as e:
        print(f"Error, ticket {ticket_number} not found")
        return None

def extract_parameters(user_message, parameters, llm_config):
    assistant_parameters = autogen.AssistantAgent(
        name="Parameter_Assistant",
        llm_config=llm_config,
        system_message=f"You are a helpful assistant that extracts the following parameters: {parameters} from a user message, return them as a json object."
    )
    user_proxy_parameters = autogen.UserProxyAgent(
        name="Parameter_User",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=1,
        code_execution_config=False,
    )

    user_proxy_parameters.initiate_chat(
        assistant_parameters,
        message=f"Extract the values for the following parameters: {parameters} from this message: '{user_message}'. Return ONLY the json.",
    )

    parameters_json = user_proxy_parameters.last_message()["content"]
    import json
    try:
      return json.loads(parameters_json)
    except Exception as e:
      print(f"Error extracting parameters: {e}")
      return None

def request_analyzer(user_message, llm_config):
    assistant_analyzer = autogen.AssistantAgent(
        name="Analyzer_Assistant",
        llm_config=llm_config,
        system_message="""You are a helpful assistant that analyzes user messages and select the right function to use.
        You have access to several functions to interact with Service Now:
        - create_servicenow_incident: Creates a new incident in Service Now.
        - request_servicenow_item: Request a specific item in the service catalog in Service Now.
        - add_comment_to_servicenow_ticket: add a comment to a ticket in service now.

        Please select the correct function for each task.
        If asked to create an incident, use the create_servicenow_incident function.
        If asked to create a request, use the request_servicenow_item function.
        If asked to add a comment to a ticket, use the add_comment_to_servicenow_ticket function.
        The function must be called with the correct parameters, you must use the extract_parameters function for this.
        The user will provide the input in natural language.
        """
    )
    user_proxy_analyzer = autogen.UserProxyAgent(
        name="Analyzer_User",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=1,
        code_execution_config=False,
        is_termination_msg=lambda x: "TERMINATE" in x.get("content", "").rstrip(),
    )

    user_proxy_analyzer.initiate_chat(
        assistant_analyzer,
        message=user_message
    )
    
    return user_proxy_analyzer.last_message()["content"]

assistant = autogen.AssistantAgent(
    name="Servicenow_assistant",
    llm_config=llm_config,
    system_message="""You are a helpful assistant that can help the user to interact with Service Now.
    You have access to several functions to interact with Service Now:
    - create_servicenow_incident: Creates a new incident in Service Now.
    - request_servicenow_item: Request a specific item in the service catalog in Service Now.
    - add_comment_to_servicenow_ticket: add a comment to a ticket in service now.

    Please select the correct function for each task.
    If asked to create an incident, use the create_servicenow_incident function.
    If asked to create a request, use the request_servicenow_item function.
    If asked to add a comment to a ticket, use the add_comment_to_servicenow_ticket function.
    You will receive the correct function and parameters to be used in a message, use them and respond with the response of the function.
    """
)

assistant.register_function(
    function_map={
        "create_servicenow_incident": create_servicenow_incident,
        "request_servicenow_item": request_servicenow_item,
        "add_comment_to_servicenow_ticket": add_comment_to_servicenow_ticket
    }
)

user_proxy = autogen.UserProxyAgent(
    name="Servicenow_user",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=10,
    is_termination_msg=lambda x: "TERMINATE" in x.get("content", "").rstrip(),
    code_execution_config=False,
)

@app.route('/api/v1/agent', methods=['POST'])
def servicenow_api():
    data = request.get_json()
    user_message = data.get('message')

    if not user_message:
        return jsonify({'error': 'No message provided'}), 400

    function_call = request_analyzer(user_message, llm_config)

    if "create_servicenow_incident" in function_call:
      parameters = extract_parameters(user_message, ["short_description", "description"], llm_config)
      response = create_servicenow_incident(parameters["short_description"], parameters["description"])
    elif "request_servicenow_item" in function_call:
      parameters = extract_parameters(user_message, ["item_name", "quantity"], llm_config)
      response = request_servicenow_item(parameters["item_name"], parameters["quantity"])
    elif "add_comment_to_servicenow_ticket" in function_call:
      parameters = extract_parameters(user_message, ["ticket_number", "comment"], llm_config)
      response = add_comment_to_servicenow_ticket(parameters["ticket_number"], parameters["comment"])
    else:
      response = None

    if response is None:
        return jsonify({"response": "Error"}), 500

    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True)
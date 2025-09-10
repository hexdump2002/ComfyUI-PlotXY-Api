import json
import urllib.request
import urllib.parse
import uuid
import requests
def queue_prompt(server_address, client_id, prompt, prompt_id):
    p = {"prompt": prompt, "client_id": client_id, "prompt_id": prompt_id}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request("http://{}/prompt".format(server_address), data=data)
    urllib.request.urlopen(req).read()

def get_image(server_address,filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen("http://{}/view?{}".format(server_address, url_values)) as response:
        return response.read()

def getModelTypes(server_address):
    with urllib.request.urlopen("http://{}/models".format(server_address)) as response:
        return json.loads(response.read())

def get_history(server_address, prompt_id):
    with urllib.request.urlopen("http://{}/history/{}".format(server_address, prompt_id)) as response:
        return json.loads(response.read())

def get_images(server_address, ws, client_id, prompt):
    prompt_id = str(uuid.uuid4())
    queue_prompt(server_address, client_id, prompt, prompt_id)
    output_images = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break #Execution is done
        else:
            # If you want to be able to decode the binary stream for latent previews, here is how you can do it:
            # bytesIO = BytesIO(out[8:])
            # preview_image = Image.open(bytesIO) # This is your preview in PIL image format, store it in a global
            continue #previews are binary data

    history = get_history(server_address,prompt_id)[prompt_id]
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        images_output = []
        if 'images' in node_output:
            for image in node_output['images']:
                image_data = get_image(server_address,image['filename'], image['subfolder'], image['type'])
                images_output.append(image_data)
        output_images[node_id] = images_output

    return output_images

# @sbszcz original
def upload_image(server_address:str, filePath:str, subfolder:str="", overwrite:bool=False):
    with open(filePath, "rb") as f:
        try:
            body = {"image": f}
            data = {}
            
            if overwrite:
                data["overwrite"] = "true"
    
            if subfolder:
                data["subfolder"] = subfolder

            resp = requests.post(f"http://{server_address}/upload/image", files=body,data=data)
            resp.raise_for_status()

            if resp.status_code == 200:
                data = resp.json()
                path = data["name"]
                if "subfolder" in data:
                    if data["subfolder"] != "":
                        path = data["subfolder"] + "/" + path
        except Exception as error:
            raise Exception(error)
    
    return path
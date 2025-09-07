#This is an example that uses the websockets api to know when a prompt execution is done
#Once the prompt execution is done it downloads the images using the /history endpoint

import websocket #NOTE: websocket-client (https://github.com/websocket-client/websocket-client)
import uuid
import json
import urllib.request
import urllib.parse
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import ImageGrid
import random
import base64
from io import BytesIO
import webbrowser
import copy
from PIL import Image
import io

server_address = "127.0.0.1:8000"
client_id = str(uuid.uuid4())

#region ComfyUI API
def queue_prompt(prompt, prompt_id):
    p = {"prompt": prompt, "client_id": client_id, "prompt_id": prompt_id}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request("http://{}/prompt".format(server_address), data=data)
    urllib.request.urlopen(req).read()

def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen("http://{}/view?{}".format(server_address, url_values)) as response:
        return response.read()

def get_history(prompt_id):
    with urllib.request.urlopen("http://{}/history/{}".format(server_address, prompt_id)) as response:
        return json.loads(response.read())

def get_images(ws, prompt):
    prompt_id = str(uuid.uuid4())
    queue_prompt(prompt, prompt_id)
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

    history = get_history(prompt_id)[prompt_id]
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        images_output = []
        if 'images' in node_output:
            for image in node_output['images']:
                image_data = get_image(image['filename'], image['subfolder'], image['type'])
                images_output.append(image_data)
        output_images[node_id] = images_output

    return output_images
#endregion

#region ComfyUI Json utils
def getNodeByName(workflowDict:dict,nodeName)->dict:
    for key, value in workflowDict.items():
        if isinstance(value, dict):
            if "_meta" in value and 'title' in value['_meta']:
                if value['_meta']['title'] == nodeName:
                    return value
            else:
                raise IndexError(f'Theres not any node with name {nodeName}')
        else:
            raise TypeError(f'The workflow {workflowDict} is not a dictionary')
        
def getNodeIdByByName(workflowDict:dict,nodeName)->int:
    for key, value in workflowDict.items():
        if isinstance(value, dict):
            if "_meta" in value and 'title' in value['_meta']:
                if value['_meta']['title'] == nodeName:
                    return key
            else:
                raise IndexError(f'Theres not any node with name {nodeName}')
        else:
            raise TypeError(f'The workflow {workflowDict} is not a dictionary')
#endregion

#region MPL grid
#Make sure len(images)==rows*cols and xAxisLabels*yAxisLabels
def buildMPLGrid(images,rows,cols, xAxisLabels, yAxisLabels):
    fig = plt.figure(figsize=(8, 80))
    grid = ImageGrid(fig, 111,
                    nrows_ncols=(rows, cols),
                    axes_pad=0.5,
                    label_mode="L",
                    share_all=True)

    # Plot each image
    i =0
    for ax, img in zip(grid, images):
        ax.imshow(img)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_xlabel(xAxisLabels[i])
        ax.set_ylabel(yAxisLabels[i])
        i+=1

    plt.show()
#endregion

def pil_to_base64(img):
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()

def getPILImagesFromComfyUIImages(images:list) -> list:
    pilImages:list = []
    for node_id in images:
        for image_data in images[node_id]:
            image = Image.open(io.BytesIO(image_data))
            # image.show()
            pilImages.append(image)
    return pilImages


def _buildPromptParamsDataForAxis(workflow:dict, axisDef) -> list:
    xAxisLabels:list=[]
    for nodeName, values in axisDef:
        for param, paramValue in values:
            node = getNodeByName(workflow,nodeName)
            if param in node['inputs']:
                val = paramValue()
                node['inputs'][param]=val
                xAxisLabels.append(param+str(val))
            else:
                raise Exception(f"Node {nodeName} doesn't have a parameter called {param}")
    return xAxisLabels
#from a workflow it generates another with the needed params changed for this comfyui generation.
#Append xAxis labels with the value you want to see in the grid fro this generation
def buildPromptParamsData(workflow:dict, valuesDef:dict, xAxisLabels:list, yAxisLabels:list) -> tuple[dict,list,list]:
    workflowCopy = copy.deepcopy(workflow)
    
    xDef=valuesDef['x']
    yDef=valuesDef['y']
    
    xAxisLabels = _buildPromptParamsDataForAxis(workflowCopy,xDef)
    yAxisLabels = _buildPromptParamsDataForAxis(workflowCopy,yDef)
        
    return workflowCopy, xAxisLabels,yAxisLabels   

getSeed= lambda: random.random.randint(0, 18446744073709551615)

workflowJsonData:str = ""
xAxisLabels = []
yAxisLabels = []
with open("workflows/basic-qwen.json") as f:
    workflowJsonData = f.read()

workflow:dict = json.loads(workflowJsonData)

allImages = []

# Grid size
rows = 2
cols = 2

ws = websocket.WebSocket()

valuesDef:dict = {
    'x': {
        'MainKSampler': {
            'seed':  getSeed
        }
    },
    'y': {
        'MainKSampler': {
            'cfg': lambda: random.uniform(1.0,3.0)
        }
    }
}

xValues, yValues = buildValues(rows, cols, valuesDef);

ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))

for rowIndex in range(rows):
    for colIndex in range(cols):
        images = get_images(ws, workflow)

        setPromptParameters(workflow, xAxisLabels, yAxisLabels)

        pilImages = getPILImagesFromComfyUIImages(images)

        allImages.extend(pilImages)

ws.close() 

webImages = []
for img in allImages:
    webImages.append(pil_to_base64(img))


col_headers = yAxisLabels
row_headers = xAxisLabels

# Build HTML
html = f"""
<!DOCTYPE html>
<html>
<head>
<style>
table {{
  border-collapse: collapse;
  font-family: sans-serif;
  text-align: center;
}}

th, td {{
  border: 1px solid #ccc;
  padding: 10px;
  vertical-align: middle;
}}

th {{
  background-color: #f0f0f0;
  font-weight: bold;
  white-space: nowrap;
}}

img {{
  max-width: 100px;
  max-height: 100px;
  border-radius: 6px;
  object-fit: cover;
}}
</style>
</head>
<body>
<table>
  <tr>
    <th></th>
"""

# Column headers
for text in col_headers:
    html += f"<th>{text}</th>"
html += "</tr>\n"

# Rows with row headers and images
for r in range(rows):
    html += f"<tr><th>{row_headers[r]}</th>"
    for c in range(cols):
        html += f'<td><img src="data:image/png;base64,{webImages[r*cols+c]}" /></td>'
    html += "</tr>\n"

html += """
</table>
</body>
</html>
"""





# Save and open
filename = "embedded_grid.html"
with open(filename, "w") as f:
    f.write(html)

webbrowser.open(filename)
import websocket
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

def getInputPropertyValue(curWorkflowNode,nodeDef,param:str,index:int):
    value = None
    paramValueDef = nodeDef[param]
    if callable(paramValueDef):
        val = paramValueDef()
    elif type(paramValueDef) is list:
        val = paramValueDef[index]
    elif type(paramValueDef) is dict:
        val = paramValueDef['setter'](curWorkflowNode['inputs'][param],nodeDef[param],index)
    else:
        val = paramValueDef
    
    return val

def _fillWorkflowForAxis(workflow:dict, axisDef,index:int) -> list:
    for nodeName, values in axisDef.items():
        i:int = 0
        for param, paramValue in values.items():
            node = getNodeByName(workflow,nodeName)
            if param in node['inputs']:
                node['inputs'][param]=getInputPropertyValue(node,values,param,index)
            else:
                raise Exception(f"Node {nodeName} doesn't have a parameter called {param}")
            i=i+1

#from a workflow it generates another with the needed params changed for this comfyui generation.
def buildWorkflow(workflow:dict, valuesDef:dict,rowIndex:int, colIndex:int) -> dict:
    workflowCopy = copy.deepcopy(workflow)
    
    xDef=valuesDef['x']
    yDef=valuesDef['y']
    
    _fillWorkflowForAxis(workflowCopy,xDef,colIndex)
    _fillWorkflowForAxis(workflowCopy,yDef,rowIndex)
        
    return workflowCopy

#After building each image with the given values we could generate its labels for 
#veritcal and horizontal values here. Right now, it only appends the param name.
def _buildLabelForAxis(workflow:dict, axisDef) -> str:
    label:str=""
    for nodeName, values in axisDef.items():
        for param, paramValue in values.items():
            node = getNodeByName(workflow,nodeName)
            if param in node['inputs']:
                if label: label+";"
                label=label+param+"="+str(node['inputs'][param])
            else:
                raise Exception(f"Node {nodeName} doesn't have a parameter called {param}")
    return label
            
'''
def _buildAxisLabelsForWorkflowIteration(workflow:dict, valuesDef:dict) -> tuple[str,str]:
    xLabel=_buildLabelForAxis(workflow, valuesDef['x'])
    yLabel=_buildLabelForAxis(workflow,valuesDef['y'])
    return xLabel,yLabel
'''

def generateAndOpenHTML(webImages:list, xLabels:list, yLabels:list):
    xLabelsSize:int = len(xLabels)
    yLabelsSize:int = len(yLabels)
    
    if len(webImages)!=xLabelsSize * yLabelsSize:
        raise ValueError(f"webImage size {len(webImages)} is not the same that xLabels*yLables {xLabelsSize*yLabelsSize}")
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
    for text in xLabels:
        html += f"<th>{text}</th>"
    html += "</tr>\n"

    # Rows with row headers and images
    for r in range(yLabelsSize):
        html += f"<tr><th>{yLabels[r]}</th>"
        for c in range(xLabelsSize):
            html += f'<td><img src="data:image/png;base64,{webImages[r*xLabelsSize+c]}" /></td>'
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

# Just play safe with javascript int range
getSeed= lambda: random.randint(0, 90071992547400)




# MAIN
# Open workflow and feed it into a dict
workflowJsonData:str = ""
with open("workflows/basic-qwen.json") as f:
    workflowJsonData = f.read()
workflow:dict = json.loads(workflowJsonData)

allImages = []

# Connect to API using websockets
ws = websocket.WebSocket()

# Veritcal and horizontal values definitions.
# rows and cols define how many images will be generated
# x/y define how values are generated for each image
valuesDef:dict = {
    'rows': 2,
    'cols': 2,
    'values': {
        'x': {
            'MainKSampler': {
                'seed': {
                    'step':2,
                    'setter': lambda oldValue,valueDef,iteration: getSeed() if iteration==0 else oldValue+valueDef['step']
                },
            }
        },
         'y': {
            'MainKSampler': {
                'cfg': [0.5,1] #round(random.uniform(1.0,3.0),1)
            }
        }
    }
}

ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))

# List that will hold the differnt labels to use in the vertical and horizontal axis
xAxisLabels=[]
yAxisLabels = []

rows= valuesDef['rows']
cols= valuesDef['cols']

for rowIndex in range(rows):
    for colIndex in range(cols):
        workflow = buildWorkflow(workflow,valuesDef['values'], rowIndex,colIndex)
        if rowIndex>=len(yAxisLabels):
            yAxisLabels.append( _buildLabelForAxis(workflow, valuesDef['values']['y']))
        if colIndex>=len(xAxisLabels): 
            xAxisLabels.append( _buildLabelForAxis(workflow, valuesDef['values']['x']))


        images = get_images(ws, workflow)
        pilImages = getPILImagesFromComfyUIImages(images)

        allImages.extend(pilImages)

ws.close() 

webImages = []
for img in allImages:
    webImages.append(pil_to_base64(img))

generateAndOpenHTML(webImages, xAxisLabels, yAxisLabels)
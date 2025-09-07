import websocket
import uuid
import json
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import ImageGrid
import random
import base64
from io import BytesIO
import webbrowser
import copy
from PIL import Image
import io
import utils.workflow as workflowUtils
import utils.comfyui_api as comfyUIUtils
import os
from pathlib import Path
import importlib.util
import sys

serverAddress = "127.0.0.1:8000"
clientId = str(uuid.uuid4())

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
            node = workflowUtils.getNodeByName(workflow,nodeName)
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
            node = workflowUtils.getNodeByName(workflow,nodeName)
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

def checkParams(args):
    if not os.path.exists(args.script):
        print(f"Error: File {args.script} couldn't be found\n")
        return False

    return True

def loadModuleFromPath(path):
    module_name = Path(path).stem
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# MAIN
import argparse

parser = argparse.ArgumentParser(description="Create a x/y visualization from a comfyui workflow (XYPlot Grid).")

# Positional argument for the script file
parser.add_argument("script", type=str, help="Path to the visualization definition. Must be a python script exporting a dict with the")

# Optional flag to save images
parser.add_argument("--save-images", action="store_true", help="Save workflow images if this flag is set")

args = parser.parse_args()

#Check if visualization file exists
result:bool = checkParams(args)
if not result: exit()

#Load script for visualization definition
visualizationDef = loadModuleFromPath(args.script).definition

# Open workflow and feed it into a dict
workflowJsonData:str = ""

with open(visualizationDef['workflow']) as f:
    workflowJsonData = f.read()
workflow:dict = json.loads(workflowJsonData)

allImages = []

# Connect to API using websockets
ws = websocket.WebSocket()

ws.connect("ws://{}/ws?clientId={}".format(serverAddress, clientId))

# List that will hold the differnt labels to use in the vertical and horizontal axis
xAxisLabels=[]
yAxisLabels = []

rows= visualizationDef['rows']
cols= visualizationDef['cols']

for rowIndex in range(rows):
    for colIndex in range(cols):
        workflow = buildWorkflow(workflow,visualizationDef['values'], rowIndex,colIndex)
        if rowIndex>=len(yAxisLabels):
            yAxisLabels.append( _buildLabelForAxis(workflow, visualizationDef['values']['y']))
        if colIndex>=len(xAxisLabels): 
            xAxisLabels.append( _buildLabelForAxis(workflow, visualizationDef['values']['x']))


        images = comfyUIUtils.get_images(serverAddress,ws, clientId, workflow)
        pilImages = getPILImagesFromComfyUIImages(images)

        allImages.extend(pilImages)

ws.close() 

webImages = []
for img in allImages:
    webImages.append(pil_to_base64(img))

generateAndOpenHTML(webImages, xAxisLabels, yAxisLabels)

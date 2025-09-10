import websocket
import uuid
import json
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import ImageGrid
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
import time
import tempfile
import html as html_lib

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

def getInputPropertyValue(previousParamData,nodeDef:dict,param:str, axisIndex:int):
    value = None
    paramValueDef = nodeDef[param]
    if callable(paramValueDef):
        val = paramValueDef(previousParamData,nodeDef[param],axisIndex)
    elif type(paramValueDef) is list:
        val = paramValueDef[axisIndex]
    else:
        val = paramValueDef
    
    return val


def _generateLabelForAxisCell(axisData) -> str:
    label:str=""
    for param, paramValue in axisData.items():
        if label: label+";"
        label=label+param+"="+str(paramValue)

    return label

def _generateGridDataForAxisCell(previousCellData:dict, axisDef:dict,axisIndex:int):
    axisData=dict()
    for nodeName, values in axisDef.items():
        axisData[nodeName]={}
        for param, paramValue in values.items():
            previousParamData = None if previousCellData is None else previousCellData[nodeName][param]
            axisData[nodeName][param]=getInputPropertyValue(previousParamData,values,param,axisIndex)
    return axisData      

def _generateGridDataForCell(gridData:dict, visualizationDef:dict, rowIndex:int, colIndex:int) -> dict:
    cellData=dict()
    
    if 'values' not in visualizationDef:
        raise ValueError('[Error] Visualization definition doesnt have a "values" key')
    if 'grid' not in visualizationDef['values']:
        raise ValueError('[Error] Values definiion doesnt have a "grid" key')
    if 'x' not in visualizationDef['values']['grid']:
        raise ValueError('[Error] Grid definition doesnt have a "x" key')
    if 'y' not in visualizationDef['values']['grid']:
        raise ValueError('[Error] Grid definition doesnt have a "y" key')
        

    xValues = visualizationDef['values']['grid']['x']
    yValues = visualizationDef['values']['grid']['y']
    
    #It is safe to access cells generated previously while generating new ones
    if rowIndex == 0:
        oldvalue = None if colIndex == 0 else gridData[0][colIndex-1]['x']
        cellData['x'] = _generateGridDataForAxisCell(oldvalue, xValues,colIndex)
    else:
        cellData['x'] = copy.deepcopy(gridData[0][colIndex]['x'])

    if colIndex==0:
        oldvalue = None if rowIndex == 0 else gridData[rowIndex-1][0]['y']
        cellData['y'] = _generateGridDataForAxisCell(oldvalue, yValues,rowIndex)
    else:
        cellData['y'] = copy.deepcopy(gridData[rowIndex][0]['y'])
   
        
    cellData['labelx'] = _generateLabelForAxisCell(cellData['x'])
    cellData['labely'] = _generateLabelForAxisCell(cellData['y'])

    return cellData

def generateGridData(rows:int, cols:int,visualizationDef:dict):
    gridData:list[list] = []
    previousCellData = None
    for rowIndex in range(rows):
        gridData.append([])
        for colIndex in range(cols):
            data = _generateGridDataForCell(gridData,visualizationDef,rowIndex,colIndex)
            gridData[rowIndex].append(data)
            previousCellData = data
    return gridData      

def _setNodePropertyValueByName(nodeName, workflow, paramName, paramValue):
    node = workflowUtils.getNodeByName(workflow,nodeName)
    if paramName in node['inputs']:
        node['inputs'][paramName]=paramValue
    else:
        raise Exception(f"Node {nodeName} doesn't have a parameter called {paramName}")


def _fillWorkflowCellData(workflow:dict, cellData:dict) -> list:
        for nodeName, values in cellData['x'].items():
            for param, paramValue in values.items():
                _setNodePropertyValueByName(nodeName,workflow,param,paramValue)
        
        for nodeName, values in cellData['y'].items():
            for param, paramValue in values.items():
                _setNodePropertyValueByName(nodeName,workflow,param,paramValue)

def _fillWorkflowInitials(workflow:dict, initialsData:dict) -> list:
    for nodeName, values in initialsData.items():
        for param, paramValue in values.items():
            _setNodePropertyValueByName(nodeName,workflow,param,paramValue)

#from a workflow it generates another with the needed params changed for this comfyui generation.
def buildWorkflowForCell(workflow:dict, gridCellData:dict,visualizationDef:dict) -> dict:
    workflowCopy = copy.deepcopy(workflow)
    
    # Apply initial values for every workflow iteration
    initialData= visualizationDef['values'].get('initialValues')
    
    if initialData: _fillWorkflowInitials(workflowCopy,initialData)
    _fillWorkflowCellData(workflowCopy,gridCellData)
        
    return workflowCopy

            
def generateAndOpenHTML(gridData:list[list], imgWidth: int, imgHeight: int):

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
    body {{
        font-family: sans-serif;
        text-align: center;
    }}
    table {{
        border-collapse: collapse;
        margin: auto;
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
        max-width: {imgWidth}px;
        max-height: {imgHeight}px;
        border-radius: 6px;
        object-fit: cover;
        cursor: pointer;
        transition: opacity 0.2s ease;
    }}
    #popupModal {{
        display: none;
        position: fixed;
        top: 0; left: 0;
        width: 100%; height: 100%;
        background-color: rgba(0,0,0,0.8);
        justify-content: center;
        align-items: center;
        z-index: 1000;
    }}
    #popupImage {{
        max-width: 90%;
        max-height: 90%;
        border-radius: 10px;
        box-shadow: 0 0 20px rgba(255,255,255,0.3);
    }}
    </style>
    </head>
    <body>

    <div id="popupModal" onclick="this.style.display='none'">
        <img id="popupImage" />
    </div>

    <table>
    <tr><th></th>
    """

    # Escape labels for HTML safety
    # xLabels = [html_lib.escape(label) for label in xLabels]
    # yLabels = [html_lib.escape(label) for label in yLabe
    
    
    # Column header
    columns=0
    firstColData = gridData[0] #first row
    for colData in firstColData:
        html += f"<th>{colData['labelx']}</th>"
        columns+=1
    html += "</tr>\n"

    # Rows with row headers and images
    for r in gridData:
        html += f"<tr><th>{r[0]['labely']}</th>"
        for c in r:
            # We support retrieving several images from a prompt. By now only get along with the first one returned
            # This support can disappear in the future. Don't know if it has any sense tu support it
            base64Image = pil_to_base64(c['image'][0]) 
            imgSrc = f"data:image/png;base64,{base64Image}"
            html += f'<td><img src="{imgSrc}" onclick="showPopup(this.src)" title="{c['labelx']} - {c['labely']}" /></td>'
        html += "</tr>\n"

    html += """
    </table>

    <script>
    function showPopup(src) {
        const modal = document.getElementById("popupModal");
        const img = document.getElementById("popupImage");
        img.src = src;
        modal.style.display = "flex";
    }
    </script>

    </body>
    </html>
    """

    # Save and open in browser
    with tempfile.NamedTemporaryFile('w', delete=False, suffix='.html') as f:
        f.write(html)
        webbrowser.open(f.name)

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

# Connect to API using websockets
ws = websocket.WebSocket()

ws.connect("ws://{}/ws?clientId={}".format(serverAddress, clientId))

# List that will hold the differnt labels to use in the vertical and horizontal axis
xAxisLabels=[]
yAxisLabels = []

rows= visualizationDef['rows']
cols= visualizationDef['cols']

totalTime=0.0

gridData: list[list] = generateGridData(rows,cols,visualizationDef)

# Resolve all resource dependencies before running the workflow
if 'resources' in visualizationDef['values']:
    if 'images' in visualizationDef['values']['resources']:
        for imagePath in visualizationDef['values']['resources']['images']:
            comfyUIUtils.upload_image(serverAddress, imagePath)

for rowIndex in range(rows):
    for colIndex in range(cols):
        print(f"[INFO] Creating image {rowIndex*cols+colIndex}")
        start = time.time()
        prompt = buildWorkflowForCell(workflow,gridData[rowIndex][colIndex],visualizationDef)
        
        images = comfyUIUtils.get_images(serverAddress,ws, clientId, prompt)
        elapsed = time.time()-start 
        print(f"[INFO] It took {elapsed:.2f} seconds")
        totalTime+=elapsed
        start = time.time()
        pilImages = getPILImagesFromComfyUIImages(images)
        gridData[rowIndex][colIndex]['image']=pilImages
        

ws.close() 

print(f"[INFO] All Done in {totalTime}")

imgWidth:int= 100
imgHeight:int = 100
if 'gridImgWidth' in visualizationDef: imgWidth = int(visualizationDef['gridImgWidth'])
if 'gridImgHeight' in visualizationDef: imgHeight = int(visualizationDef['gridImgHeight'])
generateAndOpenHTML(gridData,imgWidth,imgHeight)

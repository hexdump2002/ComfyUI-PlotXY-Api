# ComfyUI-PlotXY-Api
ComfyUI PlotXY grids using ComfyUI API on the browser (Automation example)

How to use it?

- Build a ComfyUI workflow and save it as an API workflow
- Create a visualization definition (An example in visualizations folder)
- Excute it and wait for the visualization to finish: visualize.py visualizations/qwen1.py
- When html loads you can click any image to show it at full size. Click again to get back to the image grid.

How to write a visualization definition?

Follow the visualizations/qwen1.py examples. You can use multiple params for each axis beside initial values for all prompt iterations

```
import utils.workflow as wfUtils
import random

# Veritcal and horizontal values definitions.
# rows and cols define how many images will be generated
# x/y define how values are generated for each image
definition:dict = {
    'rows': 4,
    'cols': 4,
    'gridImgWidth': 200,
    'gridImgHeight': 200,
    'workflow': 'workflows/qwen_workflow.json',
    'values': {
        # Here you set the values all workflows will run with 
        # In this particular case I want all output images to be 512x512
        'initial': {
            'EmptySD3LatentImage':{
                'width': 512,
                'height': 512
            }
        },
        # Here you define how values for both grid axis will be generated
        # There are several ways to define values for the grid. Some examples for seed param:
        # + Lambdas examples: 
        #   + 'seed': lambda oldValue,valueDef,iteration: 1 (Always return 1 for the seed along all the axis)
        #   + 'seed': lambda oldValue,valueDef,iteration: getSeed() (New seed for every cell in the axis)
        #   + 'seed': wfUtils.getSeed() if oldValue is None else oldValue+2 (generate new seed first time and keep incrementing it by to for every cell in the axis)
        # + List examples
        #   + 'seed': [0.5,1] (Take a value from the list for every axis cell. The length must be the same that rows/cols properties) )
        # + Simple value:
        # + 'seed': 3 (Same as first lambda example)
        'grid': {
            'x': {
                'MainKSampler': {
                    'seed': lambda oldValue,valueDef,iteration: 1 #wfUtils.getSeed() if oldValue is None else oldValue+2
                }
            },
            'y': {
                'MainKSampler': {
                    'cfg': lambda oldValue,valueDef,iteration: round(random.uniform(1.0,3.0),1) # [0.5,1]
                }
            }
        }
    }
}

```

Extremely experimental.

Output Example:

<img width="1622" height="990" alt="image" src="https://github.com/user-attachments/assets/4dde3c20-ec75-4368-a27c-c20e7b7a81e8" />


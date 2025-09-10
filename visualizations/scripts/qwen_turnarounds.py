import utils.workflow as wfUtils
import random

# Veritcal and horizontal values definitions.
# rows and cols define how many images will be generated
# x/y define how values are generated for each image
definition:dict = {
    'rows': 1,
    'cols': 4,
    'gridImgWidth': 200,
    'gridImgHeight': 200,
    'workflow': 'visualizations/workflows/qwen_turnarounds.json',
    'values': {
        # Add here all resources that need to be preloaded before the workflow runs
        'resources': {
            'images': ['visualizations/resources/images/dora.jpg']
        },
        # Here you set the values all workflows will run with 
        # In this particular case I want all output images to be 1024x512
        'initialValues': {
            'EmptySD3LatentImage':{
                'width': 1536,
                'height': 512
            },
            'TextEncodeQwenImageEdit': {
                'prompt':'Create a full turnaround sheet of a stylized child character designed for a cartoon game. The sheet should include four consistent views: front, back, side profile, and 3/4 angle. Ensure anatomical consistency and pose alignment across all views for use in character modeling and animation.'
            },
            'Load Image': {
                'image':'dora.jpg'
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
                'KSampler': {
                    'seed': lambda oldValue,valueDef,iteration: wfUtils.getSeed()# if oldValue is None else oldValue+2
                }
            },
            'y': {
                'KSampler': {
                    'cfg': 1 # [0.5,1]
                }
            }
        }
    }
}
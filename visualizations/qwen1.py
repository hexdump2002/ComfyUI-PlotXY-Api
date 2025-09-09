import utils.workflow as wfUtils

# Veritcal and horizontal values definitions.
# rows and cols define how many images will be generated
# x/y define how values are generated for each image
definition:dict = {
    'rows': 2,
    'cols': 1,
    'gridImgWidth': 200,
    'gridImgHeight': 200,
    'workflow': 'workflows/qwen_workflow.json',
    'values': {
        # Here you set the values all workflows will run with 
        # In this particular case I want all output images to be 1024x512
        'initial': {
            'EmptySD3LatentImage':{
                'width': 512,
                'height': 512
            }
        },
        # Here you define how values for both grid axis will be generated
        'grid': {
            'x': {
                'MainKSampler': {
                    'seed': wfUtils.getSeed
                    #'seed': {
                    #    'step':2,
                    #    'setter': getSeed() #lambda oldValue,valueDef,iteration: wfUtils.getSeed() if iteration==0 else oldValue+valueDef['step']
                    #},
                    
                }
            },
            'y': {
                'MainKSampler': {
                    'cfg': [0.5,1] #round(random.uniform(1.0,3.0),1)
                }
            }
        }
    }
}
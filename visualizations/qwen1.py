import utils.workflow as wfUtils

# Veritcal and horizontal values definitions.
# rows and cols define how many images will be generated
# x/y define how values are generated for each image
definition:dict = {
    'rows': 4,
    'cols': 4,
    'workflow': 'workflows/qwen_workflow.json',
    'values': {
        'x': {
            'MainKSampler': {
                'seed': {
                    'step':2,
                    'setter': lambda oldValue,valueDef,iteration: wfUtils.getSeed() if iteration==0 else oldValue+valueDef['step']
                },
            }
        },
         'y': {
            'MainKSampler': {
                'cfg': [0.5,1,1.5,2] #round(random.uniform(1.0,3.0),1)
            }
        }
    }
}
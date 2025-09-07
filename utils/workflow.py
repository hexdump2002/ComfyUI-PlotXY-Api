import random

# Just play safe with javascript int range
getSeed= lambda: random.randint(0, 90071992547400)

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

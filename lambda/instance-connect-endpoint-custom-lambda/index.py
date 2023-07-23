import logging
import sys
from pip._internal import main

#boto3 version used by lambda is 1.26.90 which is not latest and does not have the instanceconnectendpoint methods. 
#Remove this once boto3 is updated to 1.28.8
main(['install', '-I', '-q', 'boto3','requests', '--target', '/tmp/', '--no-cache-dir', '--disable-pip-version-check'])
sys.path.insert(0,'/tmp/')

import json
import requests
import boto3
import time

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SUCCESS = "SUCCESS"
FAILED = "FAILED"

def send(event, context, responseStatus, responseData, physicalResourceId=None, noEcho=False):
    responseUrl = event['ResponseURL']

    print(responseUrl)

    responseBody = {}
    responseBody['Status'] = responseStatus
    responseBody['Reason'] = 'See the details in CloudWatch Log Stream: ' + context.log_stream_name
    responseBody['PhysicalResourceId'] = physicalResourceId or context.log_stream_name
    responseBody['StackId'] = event['StackId']
    responseBody['RequestId'] = event['RequestId']
    responseBody['LogicalResourceId'] = event['LogicalResourceId']
    responseBody['NoEcho'] = noEcho
    responseBody['Data'] = responseData

    json_responseBody = json.dumps(responseBody)

    print("Response body:\n" + json_responseBody)

    headers = {
        'content-type' : '',
        'content-length' : str(len(json_responseBody))
    }

    try:
        response = requests.put(responseUrl,
                                data=json_responseBody,
                                headers=headers)
        print("Status code: " + response.reason)
    except Exception as e:
        print("send(..) failed executing requests.put(..): " + str(e))

def wait_until_deleted(instance_connect_endpoint_id):
    ec2_client = boto3.client('ec2')

    while True:
        try:
            response = ec2_client.describe_instance_connect_endpoints(InstanceConnectEndpointIds=[instance_connect_endpoint_id])
            if not response['InstanceConnectEndpoints']:
                # The endpoint has been deleted
                return True
            state = response['InstanceConnectEndpoints'][0]['State']
            if state == 'delete-complete':
                # The endpoint has been deleted
                return True
        except Exception as e:
            if "InvalidInstanceConnectEndpointId.NotFound" in str(e):
                # The endpoint has been deleted
                return True
            else:
                raise

        # Wait for some time before checking again
        time.sleep(5)


def handler(event, context):
    logger.info('Received event: {}'.format(event))

    request_type = event['RequestType']
    # Retrieve the properties from the custom resource event
    security_group_ids = event['ResourceProperties']['SecurityGroupIds']
    subnet_id = event['ResourceProperties']['SubnetId']

    try:
        if request_type == 'Create':
            # Create the Instance Connect endpoint
            ec2_client = boto3.client('ec2')
            response = ec2_client.create_instance_connect_endpoint(
                SecurityGroupIds=security_group_ids,
                SubnetId=subnet_id
            )

            instance_connect_endpoint_id = response['InstanceConnectEndpoint']['InstanceConnectEndpointId']
            logger.info('Instance Connect endpoint created: {}'.format(instance_connect_endpoint_id))

            # Send the success response to CloudFormation
            send(event, context, SUCCESS, {}, instance_connect_endpoint_id)
        elif request_type == 'Delete':
            # Cleanup code for deletion 
            # Delete the Instance Connect endpoint
            ec2_client = boto3.client('ec2')
            instance_connect_endpoint_id = event['PhysicalResourceId']
            endpoint_exist=ec2_client.describe_instance_connect_endpoints(
                InstanceConnectEndpointIds=[instance_connect_endpoint_id]
               )
            if endpoint_exist['InstanceConnectEndpoints'][0]['InstanceConnectEndpointId'] == instance_connect_endpoint_id:
                
                state = endpoint_exist['InstanceConnectEndpoints'][0]['State']

                not_allowed_states = ['create-in-progress',  'create-failed', 'delete-in-progress',  'delete-failed']

                if state  in not_allowed_states:
                    # If the state is not 'create-complete', send a failure response to CloudFormation
                    error_message = {
                        'Status': f"Invalid state: {state}. The custom resource is not in 'create-complete' state during stack deletion."
                    }
                    send(event, context, FAILED, error_message, instance_connect_endpoint_id)
                    return

                # The state is 'create-complete', proceed with the deletion
                response=ec2_client.delete_instance_connect_endpoint(
                    InstanceConnectEndpointId=instance_connect_endpoint_id
               )
                wait_until_deleted(instance_connect_endpoint_id)

            # Send the success response to CloudFormation
            send(event, context, SUCCESS,{}, instance_connect_endpoint_id)
        else:
            # For Update
            ec2_client = boto3.client('ec2')
            instance_connect_endpoint_id = event['PhysicalResourceId']
            response=ec2_client.describe_instance_connect_endpoints(
                InstanceConnectEndpointIds=[instance_connect_endpoint_id]
               )
        
            # Send the success response to CloudFormation
            send(event, context, SUCCESS,{}, instance_connect_endpoint_id)


    except Exception as e:
        logger.error('Failed to process custom resource: {}'.format(str(e)))
        # Send the failure response to CloudFormation
        send(event, context, FAILED, {}, str(e))

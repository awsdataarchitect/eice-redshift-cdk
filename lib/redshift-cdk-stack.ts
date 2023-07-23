import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as redshift from 'aws-cdk-lib/aws-redshift';
import { DBNAME, MASTER_USERNAME, MASTER_PASSWORD, NODE_TYPE , NO_OF_NODES, PORT } from './cdk-parameters';

export class RedshiftCdkStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // VPC
    const vpc = new ec2.Vpc(this, 'MyVPC', {
      cidr: '10.0.0.0/16',
      subnetConfiguration: [
        {
          name: 'Private',
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
          cidrMask: 24,
        },
      ],
    });


    // Private Subnet
    const privateSubnet = vpc.selectSubnets({ subnetType: ec2.SubnetType.PRIVATE_ISOLATED }).subnetIds[0];


    // Security Group for Instance Connect Endpoint
    const instanceConnectSG = new ec2.SecurityGroup(this, 'InstanceConnectSecurityGroup', {
      vpc,
      allowAllOutbound: false, // Set allowAllOutbound to false for customized outbound rules
    });


    // Security Group for Redshift Cluster
    const redshiftSG = new ec2.SecurityGroup(this, 'RedshiftSecurityGroup', {
      vpc,
      allowAllOutbound: false, // Set allowAllOutbound to false for customized outbound rules
    });

    // Add inbound rule to allow SSH from Instance Connect SG to EC2 SG
    redshiftSG.addIngressRule(instanceConnectSG, ec2.Port.tcp(3389), 'Allow access from Instance Connect SG');

    // Add outbound rule to allow SSH from Instance Connect SG to EC2 SG
    instanceConnectSG.addEgressRule(redshiftSG, ec2.Port.tcp(3389), 'Allow access to Redshift SG');

    // Create the custom resource lambda function
    const instanceConnectEndpointProvider = new lambda.SingletonFunction(this, 'InstanceConnectEndpointProvider', {
      uuid: 'ab33dd90-4c45-11ec-8d3d-0242ac130003', // Generate a unique UUID
      lambdaPurpose: 'Lambda function for CFN custom resource - EC2 Instance Connect Endpoint',
      functionName: 'InstanceConnectEndpointProviderCustomResource',
      runtime: lambda.Runtime.PYTHON_3_9,
      code: lambda.Code.fromAsset('lambda/instance-connect-endpoint-custom-lambda'), // Path to your Lambda function code
      handler: 'index.handler',
      timeout: cdk.Duration.minutes(5),
    });

    instanceConnectEndpointProvider.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          "ec2:CreateInstanceConnectEndpoint",
          "ec2:CreateNetworkInterface",
          "ec2:DeleteInstanceConnectEndpoint",
          "ec2:CreateTags",
          "iam:CreateServiceLinkedRole",
          'ec2:Describe*'],
        resources: ['*'], // Update with specific resources if needed
      })
    );

    // Create the custom resource to invoke the lambda function
    const instanceConnectEndpointProviderResource = new cdk.CustomResource(this, 'InstanceConnectEndpointProviderResource', {
      serviceToken: instanceConnectEndpointProvider.functionArn,
      properties: {
        SecurityGroupIds: [instanceConnectSG.securityGroupId],
        SubnetId: privateSubnet,
        Status: '', // Initialize the Status property
      },

    });

    // Create the Redshift Cluster Subnet Group
    const subnetGroup = new redshift.CfnClusterSubnetGroup(this, 'MyRedshiftSubnetGroup', {
      description: 'Redshift cluster subnet group',
      subnetIds: [privateSubnet],
    });

    // Create the Redshift Cluster
    const cluster = new redshift.CfnCluster(this, 'MyRedshiftCluster', {
      clusterType: 'single-node', // Single-node cluster
      dbName: DBNAME, // Replace with your desired database name
      masterUsername: MASTER_USERNAME, // Replace with your desired master username
      masterUserPassword: MASTER_PASSWORD, // Replace with your desired password
      nodeType: NODE_TYPE, // Smallest and cheapest node type
      numberOfNodes: NO_OF_NODES, // Single-node, change to 2 for multi-node
      vpcSecurityGroupIds: [redshiftSG.securityGroupId], // Use the default security group
      clusterSubnetGroupName: subnetGroup.ref, // Use the created subnet group
      publiclyAccessible: false,
      port: PORT,
    });


    // Outputs
    new cdk.CfnOutput(this, 'RedshiftClusterEndpoint', {
      value: cluster.attrEndpointAddress,
      description: 'Redshift Cluster Endpoint',
    });

  }
}
